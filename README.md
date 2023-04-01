# Network-Application-Development-Coursework

## A University Networks Coursework to develop 5 simple network-based applications:
  1. ping
  2. traceroute
  3. paris-traceroute
  4. web server (the localhost will act as a web server)
  5. proxy (the localhost will act as a proxy)
  
 ## Prerequisite to run the code
  - Having python installed on your machine
  - It is better if you run the code on a linux machine (or a virtual machine containing linux), because some of the features doesn't work properly in Windows


## How to run the code
  - Clone this repo into your local machine
  - If you want to run ping type the following command
    - python3 NetworkApplications.py ping "website"
    - example: python3 NetworkApplications.py ping www.google.com
    
    <br />
  - If you want to run traceroute type the following command
    - python3 NetworkApplications.py traceroute "website"
    - example: python3 NetworkApplications.py traceroute www.google.com
    
    <br />
  - If you want to run pairs-traceroute type the following command
    - python3 NetworkApplications.py paris-traceroute "website"
    - example: python3 NetworkApplications.py paris-traceroute www.google.com
    
    <br />
  - If you want to run web server type the following command (you can configure the port -- optional)
    - python3 NetworkApplications.py web [--port]
    - example: python3 NetworkApplications.py web --port 1234
    
    <br />
  - If you want to run proxy type the following command (you can configure te port -- optional)
    - python3 NetworkApplications.py proxy [--port]
    - example: python3 NetworkApplications.py proxy --port 1234
    
<br />
## Testing if web server functionality is working
  - open a separate command line window and use curl (Client URL) to communicate with the web server
  - type the following command "curl 127.0.0.1:[port]/index.html" <br />
    ![App Screenshoot](https://github.com/youssef-gerges-ramzy-mokhtar/Network-Application-Development-Coursework/blob/main/screenshots/web%201.png) <br />
    ![App Screenshoot](https://github.com/youssef-gerges-ramzy-mokhtar/Network-Application-Development-Coursework/blob/main/screenshots/web%202.png)

<br />
## Testing if proxy functionality is working
  - open a separate command line window and use curl (Client URL) to communicate with the proxy server
  - type the following command "curl url --proxy 127.0.0.1:[port]"
  - Note: the proxy feature developed can only support websites that use HTTP/1.1 protocol 
  - ![App Screenshoot](https://github.com/youssef-gerges-ramzy-mokhtar/Network-Application-Development-Coursework/blob/main/screenshots/proxy%201.png)
  - ![App Screenshoot](https://github.com/youssef-gerges-ramzy-mokhtar/Network-Application-Development-Coursework/blob/main/screenshots/proxy%202.png)
  
  
