#!/usr/bin/env python3
    # -- coding: UTF-8 --

import argparse
import socket
import os
import sys
import struct
# from time import time, ctime, sleep
import time
from time import time, ctime, sleep
import random
import traceback # useful for exception handling
import threading
import select
import ipaddress

def setupArgumentParser() -> argparse.Namespace:
        parser = argparse.ArgumentParser(
            description='A collection of Network Applications developed for SCC.203.')
        parser.set_defaults(func=ICMPPing, hostname='www.lancaster.ac.uk')
        subparsers = parser.add_subparsers(help='sub-command help')
        
        parser_p = subparsers.add_parser('ping', aliases=['p'], help='run ping')
        parser_p.set_defaults(timeout=4)
        parser_p.add_argument('hostname', type=str, help='host to ping towards')
        parser_p.add_argument('--count', '-c', nargs='?', type=int,
                                help='number of times to ping the host before stopping')
        parser_p.add_argument('--timeout', '-t', nargs='?',
                                type=int,
                                help='maximum timeout before considering request lost')
        parser_p.set_defaults(func=ICMPPing)

        parser_t = subparsers.add_parser('traceroute', aliases=['t'],
                                            help='run traceroute')
        parser_t.set_defaults(timeout=4, protocol='icmp')
        parser_t.add_argument('hostname', type=str, help='host to traceroute towards')
        parser_t.add_argument('--timeout', '-t', nargs='?', type=int,
                                help='maximum timeout before considering request lost')
        parser_t.add_argument('--protocol', '-p', nargs='?', type=str,
                                help='protocol to send request with (UDP/ICMP)')
        parser_t.set_defaults(func=Traceroute)
        
        parser_pt = subparsers.add_parser('paris-traceroute', aliases=['pt'],
                                            help='run paris-traceroute')
        parser_pt.set_defaults(timeout=4, protocol='icmp')
        parser_pt.add_argument('hostname', type=str, help='host to traceroute towards')
        parser_pt.add_argument('--timeout', '-t', nargs='?', type=int,
                                help='maximum timeout before considering request lost')
        parser_pt.add_argument('--protocol', '-p', nargs='?', type=str,
                                help='protocol to send request with (UDP/ICMP)')
        parser_pt.set_defaults(func=ParisTraceroute)

        parser_w = subparsers.add_parser('web', aliases=['w'], help='run web server')
        parser_w.set_defaults(port=8080)
        parser_w.add_argument('--port', '-p', type=int, nargs='?',
                                help='port number to start web server listening on')
        parser_w.set_defaults(func=WebServer)

        parser_x = subparsers.add_parser('proxy', aliases=['x'], help='run proxy')
        parser_x.set_defaults(port=8000)
        parser_x.add_argument('--port', '-p', type=int, nargs='?',
                                help='port number to start web server listening on')
        parser_x.set_defaults(func=Proxy)

        args = parser.parse_args()
        return args


class NetworkApplication:

    def checksum(self, dataToChecksum: str) -> str:
        csum = 0
        countTo = (len(dataToChecksum) // 2) * 2
        count = 0

        while count < countTo:
            thisVal = dataToChecksum[count+1] * 256 + dataToChecksum[count]
            csum = csum + thisVal
            csum = csum & 0xffffffff
            count = count + 2

        if countTo < len(dataToChecksum):
            csum = csum + dataToChecksum[len(dataToChecksum) - 1]
            csum = csum & 0xffffffff

        csum = (csum >> 16) + (csum & 0xffff)
        csum = csum + (csum >> 16)
        answer = ~csum
        answer = answer & 0xffff
        answer = answer >> 8 | (answer << 8 & 0xff00)

        answer = socket.htons(answer)

        return answer

    def printOneResult(self, destinationAddress: str, packetLength: int, time: float, ttl: int, destinationHostname=''):
        if destinationHostname:
            print("%d bytes from %s (%s): ttl=%d time=%.2f ms" % (packetLength, destinationHostname, destinationAddress, ttl, time))
        else:
            print("%d bytes from %s: ttl=%d time=%.2f ms" % (packetLength, destinationAddress, ttl, time))

    def printAdditionalDetails(self, packetLoss=0.0, minimumDelay=0.0, averageDelay=0.0, maximumDelay=0.0):
        print("%.2f%% packet loss" % (packetLoss))
        if minimumDelay > 0 and averageDelay > 0 and maximumDelay > 0:
            print("rtt min/avg/max = %.2f/%.2f/%.2f ms" % (minimumDelay, averageDelay, maximumDelay))

    def printMultipleResults(self, ttl: int, destinationAddress: str, measurements: list, destinationHostname=''):
        latencies = ''
        noResponse = True
        for rtt in measurements:
            if rtt is not None:
                latencies += str(round(rtt, 3))
                latencies += ' ms  '
                noResponse = False
            else:
                latencies += '* ' 

        if noResponse is False:
            print("%d %s (%s) %s" % (ttl, destinationHostname, destinationAddress, latencies))
        else:
            print("%d %s" % (ttl, latencies))

class ICMPPing(NetworkApplication):
    current_seq_num = 0
    sending_time = 0

    def receiveOnePing(self, icmpSocket, destinationAddress, ID, timeout):
        # 1. Wait for the socket to receive a reply
        ready = select.select([icmpSocket], [], [], timeout)
        if ready[0]:
            echo_response = icmpSocket.recv(1000) # will receive at most 100 bytes
        else:
            return -1

        # 2. Once received, record time of receipt, otherwise, handle a timeout
        receiving_time = time()

        # 3. Compare the time of receipt to time of sending, producing the total network delay
        delay = receiving_time - self.sending_time

        # 4. Unpack the packet header for useful information, including the ID
        icmpHeader = echo_response[20:28]
        type, code, checksum, rec_ID, seq_num = struct.unpack("!BBHHH", icmpHeader)

        # 5. Check that the ID matches between the request and reply
        if (ID != rec_ID):
            return -1

        # 6. Return total network delay
        ttl = struct.unpack("!BBHHHBBHII", echo_response[0:20])[5] # we are extracting the ttl from the ip header
        return [1000*delay, ttl]

    def sendOnePing(self, icmpSocket, destinationAddress, ID):
        # 1. Build ICMP header
        # struct.pack is putting same values together as if it is a C Structure
        # we should have a structure containg the following: 
            # Type = 8 on wireshark --- (8 bits)
            # Code = 0 on wireshark --- (8 bits)
            # Checksum = will be calculated after creating the structure -- (16 bits)
            # Identifier = can contain any value and is used to identify the packet --- (16 bits)
            # Sequence Number = on wireshark each packet send seq_num is incremented from the previous packet --- (16 bits)
        self.current_seq_num += 1
        data = bytes("abcdefghijklmnopqrstuvwabcdefghi", "ascii") # here we are sending 32 bytes
        icmp_packet = struct.pack("!BBHHH", 8, 0, 0, ID, self.current_seq_num) + data # The form '!' represents the network byte order which is always big-endian as defined in IETF RFC 1700.

        # 2. Checksum ICMP packet using given function
        checksum_res = self.checksum(icmp_packet)

        # 3. Insert checksum into packet
        icmp_packet = struct.pack("!BBHHH", 8, 0, socket.htons(checksum_res), ID, self.current_seq_num) + data

        # 4. Send packet using socket
        icmpSocket.sendto(icmp_packet, (destinationAddress, 1))

        # 5. Record time of sending
        self.sending_time = time()


    def doOnePing(self, destinationAddress, timeout):
        # 1. Create ICMP socket
        icmp_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.getprotobyname("icmp"));
        # print(icmp_socket)

        # 2. Call sendOnePing function
        self.sendOnePing(icmp_socket, destinationAddress, 1)

        # 3. Call receiveOnePing function
        delay = self.receiveOnePing(icmp_socket, destinationAddress, 1, timeout)

        # 4. Close ICMP socket
        icmp_socket.close()

        # 5. Return total network delay
        return delay   

    def __init__(self, args):
        print('Ping to: %s...' % (args.hostname))

        # 1. Look up hostname, resolving it to an IP address
        ip = socket.gethostbyname(args.hostname)

        # 2. Call doOnePing function, approximately every second
        for i in range(4): # 4. Continue this process until stopped 
            info = self.doOnePing(ip, 5)
            if (info[0] < 0):
                print("Timeout")
                continue

            # 3. Print out the returned delay (and other relevant details) using the printOneResult method
            self.printOneResult(ip, 32, round(info[0]), info[1])
            sleep(1)

class Traceroute(NetworkApplication):
    current_seq_num = 0
    sending_time = 0
    id = 1

    def receiveOnePing(self, icmpSocket, destinationAddress, ID, timeout):
        # 1. Wait for the socket to receive a reply
        ready = select.select([icmpSocket], [], [], timeout)
        if ready[0]:
            echo_response = icmpSocket.recv(2000) # will receive at most 2000 bytes
        else:
            return -1

        # 2. Once received, record time of receipt, otherwise, handle a timeout
        receiving_time = time()

        # 3. Compare the time of receipt to time of sending, producing the total network delay
        delay = receiving_time - self.sending_time

        # 4. Unpack the packet header for useful information, including the ID
        icmpHeader = echo_response[20:28]
        type, code, checksum, rec_ID, seq_num = struct.unpack("!BBHHH", icmpHeader)

        # 6. Return total network delay & Source IP Address
        return [1000*delay, echo_response[12:16]]

    def sendOnePing(self, icmpSocket, destinationAddress, ID):
        # 1. Build ICMP header
        # struct.pack is putting same values together as if it is a C Structure
        # we should have a structure containg the following: 
            # Type = 8 on wireshark --- (8 bits)
            # Code = 0 on wireshark --- (8 bits)
            # Checksum = will be calculated after creating the structure -- (16 bits)
            # Identifier = can contain any value and is used to identify the packet --- (16 bits)
            # Sequence Number = on wireshark each packet send seq_num is incremented from the previous packet --- (16 bits)
        self.current_seq_num += 1
        data = bytes("abcdefghijklmnopqrstuvwabcdefghi", "ascii")
        icmp_packet = struct.pack("!BBHHH", 8, 0, 0, ID, self.current_seq_num) + data # The form '!' represents the network byte order which is always big-endian as defined in IETF RFC 1700.

        # 2. Checksum ICMP packet using given function
        checksum_res = self.checksum(icmp_packet)

        # 3. Insert checksum into packet
        icmp_packet = struct.pack("!BBHHH", 8, 0, socket.htons(checksum_res), ID, self.current_seq_num) + data

        # 4. Send packet using socket
        icmpSocket.sendto(icmp_packet, (destinationAddress, 1))

        # 5. Record time of sending
        self.sending_time = time()

    def doOnePing(self, destinationAddress, timeout, ttl):
        # 1. Create ICMP socket
        icmp_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.getprotobyname("icmp"));
        icmp_socket.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl)

        # 2. Call sendOnePing function
        self.sendOnePing(icmp_socket, destinationAddress, self.id)
        self.id += 1

        # 3. Call receiveOnePing function
        delay = self.receiveOnePing(icmp_socket, destinationAddress, 1, timeout)

        # 4. Close ICMP socket
        icmp_socket.close()

        # 5. Return total network delay
        return delay   


    def __init__(self, args):
        # Please ensure you print each result using the printOneResult method!
        print('Traceroute to: %s...' % (args.hostname))

        # 1. Look up hostname, resolving it to an IP address
        dest_ip = socket.gethostbyname(args.hostname)

        ttl_count = 1
        hop_id = -1
        while dest_ip != hop_id and ttl_count < 30:
            info = self.doOnePing(dest_ip, 3, ttl_count)
            if info == -1:
                print("* * *")
            else:
                hop_id = socket.inet_ntoa(info[1]) # this converts the binary value of the ip address to a readable string representing the ip 
                self.printOneResult(hop_id, 32, round(info[0]), ttl_count)
            
            ttl_count += 1

        print("Trace complete.")


class ParisTraceroute(NetworkApplication):
    source_port = 33457
    destination_port = 33456 
    sendingTime = None
    cur_checksum = 0

    def createSendingSocket(self, hostname, ttl): # This is a UDP Socket
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.getprotobyname("UDP"))
        udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        udp_socket.bind(("0.0.0.0", self.source_port))
        udp_socket.connect((hostname, self.destination_port))
        udp_socket.setsockopt(socket.SOL_IP, socket.IP_TTL, ttl)

        return udp_socket

    def createRecevingScoket(self): # This is a ICMP Socket
        icmp_socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.getprotobyname("icmp"))
        return icmp_socket

    def sendOnePing(self, udp_socket, destination_address, ttl):
        udp_socket.sendto(struct.pack("!H", 0xff76), (destination_address, self.destination_port))
        self.sendingTime = time()

    def receiveOnePing(self, icmpSocket, destinationAddress, ID, timeout):
        # 1. Wait for the socket to receive a reply
        ready = select.select([icmpSocket], [], [], timeout)
        if ready[0]:
            echo_response = icmpSocket.recv(2048) # will receive at most 2000 bytes
        else:
            return None

        # 2. Once received, record time of receipt, otherwise, handle a timeout
        receiving_time = time()

        # 3. Compare the time of receipt to time of sending, producing the total network delay
        delay = receiving_time - self.sendingTime

        # 4. Unpack the packet header for useful information, including the ID
        icmpHeader = echo_response[20:28]
        type, code, checksum, rec_ID, seq_num = struct.unpack("!BBHHH", icmpHeader)

        # 6. Return total network delay & Source IP Address
        return [1000*delay, echo_response[12:16]]

    def closeSockets(self, sockets):
        for cur_socket in socket:
            cur_socket.close()
    
    def __init__(self, args):
        print("Paris-Traceroute to: %s..." % (args.hostname))
        dest_ip = socket.gethostbyname(args.hostname)

        for ttl in range(1, 30):
            udp_socket = self.createSendingSocket(dest_ip, ttl)
            icmp_socket = self.createRecevingScoket()
            self.sendOnePing(udp_socket, dest_ip, ttl)
            packet_info = self.receiveOnePing(icmp_socket, None, None, args.timeout)
            if packet_info == None:
                print("* * *")
            else:
                hop_id = socket.inet_ntoa(packet_info[1])
                # print(packet_info[0], hop_id)
                self.printOneResult(hop_id, 2, round(packet_info[0]), ttl)
                if hop_id == dest_ip:
                    break


class WebServer(NetworkApplication):
    def handleRequest(self, tcpSocket):
        # 1. Receive request message from the client on connection socket
        request = tcpSocket.recv(1024)
        print(request)

        # 2. Extract the path of the requested object from the message (second part of the HTTP header)
        file_path = request.split()[1].decode() # default seperator is white space 
        print(request.split())
 
        # 3. Read the corresponding file from disk
        outputdata = ""
        response = ""
        try:
            file = open(file_path[1:], "r")
            
            # 4. Store in temporary buffer
            outputdata = file.read().encode() # convert string to binary 
            file.close()

            response = "HTTP/1.1 200 OK\r\n\r\n".encode()
        except FileNotFoundError:
            print("File Not Found")
            response = "HTTP/1.1 404 Not Found\r\n\r\n".encode()

        # 5. Send the correct HTTP response error
        tcpSocket.sendall(response)

        # 6. Send the content of the file to the socket
        tcpSocket.sendall(outputdata)

        tcpSocket.close()

    def __init__(self, args):
        print('Web Server starting on port: %i...' % (args.port))
        # 1. Create server socket
        serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # 2. Bind the server socket to server address and server port
        serverSocket.bind(("localhost", args.port)) # I need to extract the server port from args

        # 3. Continuously listen for connections to server socket
        serverSocket.listen()

        # 4. When a connection is accepted, call handleRequest function, passing new connection socket (see https://docs.python.org/3/library/socket.html#socket.socket.accept)
        while True:
            connectionSocket, address = serverSocket.accept()
            self.handleRequest(connectionSocket)

        # 5. Close server socket
        serverSocket.close()


class Proxy(NetworkApplication):
    # Localhost is the default name of the computer you are working on. The term is a pseudo name for 127.0. 0.1, 
    # the IP address of the local computer. This IP address allows the machine to connect to and communicate with itself
    max_data_to_receive = 5000

    def createProxySocket(self):
        proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        proxy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        proxy_socket.bind(("localhost", args.port))
        proxy_socket.listen()

        return proxy_socket

    def getRequestInfo(self, clientSocket):
        client_request = clientSocket.recv(self.max_data_to_receive).decode()        
        hostname = client_request.split()[4].replace("www.", "")
        print("Client Request: ", client_request)
        return [hostname, client_request]

    def createServerScoket(self, hostname):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print("Hostname is = ", hostname)
        server_socket.connect((hostname, 80))  # http uses port 80 that is why we are using it here

        return server_socket
    
    def cacheServerResponse(self, serverResponse, hostname): # read about the cache also 
        fileResponse = open(hostname, "w")
        fileResponse.write(serverResponse.decode())
        fileResponse.close()

    def sendRequestToServer(self, serverSocket, clientRequestInfo):
        hostname, clientRequest = clientRequestInfo
        server_response = None

        if (os.path.isfile(hostname)):
            requestFile = open(hostname, "rb")
            server_response = requestFile.read()
            requestFile.close()  
            print("Cached Before")
        else:
            serverSocket.sendall(clientRequestInfo[1].encode())
            server_response = serverSocket.recv(self.max_data_to_receive)
            self.cacheServerResponse(server_response, hostname)
            print("File not found")


        serverSocket.close()
        return server_response

    def sendResponsetoClient(self, clientSocket, serverResponse):
        print("Sending response to client")
        clientSocket.sendall(serverResponse)
        clientSocket.close()

    def __init__(self, args):
        print('Web Proxy starting on port: %i...' % (args.port))
        proxy_socket = self.createProxySocket()

        while True:
            client_socket, address = proxy_socket.accept() # socket.accept() returns a tuple containing the connection socket and the connection address
            print(f"Received connection from {address}")

            request_info = self.getRequestInfo(client_socket) # request info will contain the server url and the full client request
            print("Server Info: ", request_info)
            server_socket = self.createServerScoket(request_info[0])
            self.sendResponsetoClient(client_socket, self.sendRequestToServer(server_socket, request_info))

        proxy_socket.close()


if __name__ == "__main__":
    args = setupArgumentParser()
    args.func(args)
