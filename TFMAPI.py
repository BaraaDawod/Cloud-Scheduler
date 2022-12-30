import threading
import subprocess
import sys
import os
import time
import datetime
import handler
from pathlib import Path
import multiprocessing
import socket
import Protocol
import re
import queue

# https://stackoverflow.com/questions/70013734/how-to-share-data-between-multiple-python-environments-and-active-scripts-contro


class TFMAPI():
    def __init__(self, request_folder, response_folder, service_object, hard_coded_venv_list=['base', 'portoptvenv']):
        self.request_folder = request_folder
        self.response_folder = response_folder
        self.service_object = service_object
        self.hard_coded_venv_list = hard_coded_venv_list
        self.child_venv_script = "C:\\Source\\Repo\\TotalFundManagement\\bcitfm\\api\\ChildVenv.py"
        current_day = datetime.datetime.now().strftime("%Y-%m-%d")
        self.log_directory = f"\\\\bcimcs8.corp.bcimc.com\\sharedir\\TFM\\Programs\\PROD\\bcitfm\\api\\logs\\log_{current_day}.txt"
        self.venv_dedicated_folder_dic = {}
        self.venv_communication = {}
        self.print_queue = multiprocessing.Queue()
        self.connection_port = None
        self.thread_close_queue = queue.Queue()

    def create_child_venv(self):
        """
        Description: Get list of installed virtual environments and start a thread for each one if they are in the hardcoded list
        Parameters: None
        Return:
            - venv_dedicated_folder_dic: Key=venv; Value=dedicated venv subdirectory
        """
        # env_list = self.hard_coded_venv_list
        # https://stackoverflow.com/questions/47229025/windows-services-cant-create-subprocesses
        # Get list of all installed virtual environments
        # process = subprocess.run(['cmd', 'call', 'conda.bat', 'env', 'list'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
        # env_list = (process.stdout.splitlines())[2:]
        # env_list = [re.split('\s+', tmp.decode())[0] for tmp in env_list if len(re.split('\s+', tmp.decode())) > 1]
        env_list = os.popen(cmd = 'call conda.bat env list').read()
        env_list = [ y for y in [' '.join(x.split()) for x in env_list.split('\n')[2:] if len(x) > 1] if len(y.split(' ')) > 1]
        env_list = [tmp.split(" ")[0] for tmp in env_list]
        # Create a thread to be in charge of each venv
        for venv in env_list:
            if venv in self.hard_coded_venv_list:
                # Make a dedicated subdirectory in the request folder for each venv
                self.venv_dedicated_folder_dic[venv] = f"{self.request_folder}\\{venv}"
                self.print_queue.put(self.venv_dedicated_folder_dic[venv])
                self.venv_communication[venv] = {}
                self.venv_communication[venv]['connection_alive'] = False
                self.venv_communication[venv]['subprocess_alive'] = False
                Path(self.venv_dedicated_folder_dic[venv]).mkdir(parents=True, exist_ok=True)

                # Start a thread for each venv
                temp_thread = threading.Thread(target=self.subprocess_thread, args=(venv, self.venv_dedicated_folder_dic[venv]))
                temp_thread.daemon = True
                temp_thread.start()

    def subprocess_thread(self, venv, venv_dedicated_request_folder):
        """
        Description: Receive list of installed virtual environments and start a thread for each one if they are in the hardcoded list
        Parameters: 
            - venv: Virtual Environment
            - venv_dedicated_request_folder: Dedicated venv subdirectory
        Return: None
        """

        # Use conda on VM or local computer
        # command = ['powershell', 'conda', 'activate', venv, ';', 'python', self.child_venv_script, venv, venv_dedicated_request_folder, self.response_folder, str(self.connection_port)]
        
        # Use conda.bat on file server
        command = ['powershell', 'conda', 'activate', venv, ';', 'python', self.child_venv_script, venv, venv_dedicated_request_folder, self.response_folder, str(self.connection_port)]
        
        # Create subprocess in specified venv
        self.venv_communication[venv]['subprocess_alive'] = True
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL) as process:
            for line in process.stdout:
                self.print_queue.put(line.decode().strip())

        self.venv_communication[venv]['subprocess_alive'] = False
        
        if process.returncode != 0:
            string = f"Error! Code: {process.returncode}. Subprocess '{venv}' has crashed unexpectedly"
            self.print_queue.put(string)
            
        string = f"Shutting down subprocess '{venv}'."
        self.print_queue.put(string)

    def print_log(self, string):
        with open(self.log_directory, 'a') as myfile:
            current_datetime = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            output_string = f"{current_datetime}: {string}\n"
            myfile.write(output_string)

    def server_socket(self):
        socket_connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        socket_connection.bind(("localhost", 0))
        self.connection_port = socket_connection.getsockname()[1]
        self.print_queue.put(f"Connection Port:{self.connection_port}")
        socket_connection.listen(5)

        while True:
            # now our endpoint knows about the OTHER endpoint.
            sock, address = socket_connection.accept()
            self.print_queue.put(f"Connection with {address} has been established.")
            temp_thread = threading.Thread(target=self.client_receiver, args=(sock, address))
            temp_thread.daemon = True
            temp_thread.start()

    def client_receiver(self, sock, address):
        venv = ""
        # send init
        sock.send(Protocol.INITIALIZE.encode())
        # get venv
        init_response = sock.recv(1024).decode()
        if Protocol.VENV in init_response:
            venv = init_response.split("|")[1]
        else:
            # Close connection
            sock.close()
            self.print_queue.put(f"Conncetion with {venv} closed")
            return
        
        self.venv_communication[venv]['connection_alive'] = True
        # Get data
        sock.send(Protocol.APPROVE.encode())
        
        sock.settimeout(60)
        while True:
            try:
                data_packet = sock.recv(1024)
                if not data_packet:
                    self.print_queue.put(f"Conncetion with {venv} closed. Attempting to restart")
                    break
                
                data_packet = data_packet.decode()
                if Protocol.DATA in data_packet:
                    self.print_queue.put(f"{venv} | Packet: {data_packet}")
                elif Protocol.ERROR in data_packet:
                    self.print_queue.put(f"{venv} | Packet: {data_packet}")
                elif Protocol.TEST_CONNECTION in data_packet:
                    # Uncomment to test if connection is maintained
                    # self.print_queue.put(f"{venv} | {Protocol.TEST_CONNECTION}")
                    continue
                elif Protocol.CLOSE in data_packet:
                    self.print_queue.put(f"Conncetion with {venv} closed")
                    self.venv_communication[venv]['connection_alive'] = False
                    return
                    
            except TimeoutError:
                continue
            except ConnectionAbortedError:
                self.print_queue.put(f"Conncetion with {venv} closed")
                self.venv_communication[venv]['connection_alive'] = False
                return
            except ConnectionResetError:
                self.print_queue.put(f"Conncetion with {venv} closed")
                self.venv_communication[venv]['connection_alive'] = False
                return
            
    def restart_subprocess(self, venv):
        temp_thread = threading.Thread(target=self.subprocess_thread, args=(venv, self.venv_dedicated_folder_dic[venv]))
        temp_thread.daemon = True
        temp_thread.start()
        
    def run(self):
        # # Setup server socket
        temp_thread = threading.Thread(target=self.server_socket, args=())
        temp_thread.daemon = True
        temp_thread.start()

        # Find avaliable virtual environments
        self.create_child_venv()
        handler.create_master_watchdog(self.print_queue, self.venv_dedicated_folder_dic, self.request_folder, self.response_folder)

        while not self.service_object.stop_requested:
            while not self.print_queue.empty():
                self.print_log(self.print_queue.get())

            # Restart child venvs if they crash
            for key in self.venv_communication:
                if not self.venv_communication[key]['subprocess_alive']:
                    # Restart subprocess
                    self.restart_subprocess(key)
            time.sleep(1)

class TestServiceObject():
    def __init__(self):
        self.stop_requested = False


if __name__ == "__main__":
    req = "C:\\Source\\Repo\\TotalFundManagement\\bcitfm\\api\\request"
    resp = "C:\\Source\\Repo\\TotalFundManagement\\bcitfm\\api\\response"
    req_2 = "\\\\bcimcs8.corp.bcimc.com\\sharedir\\TFM\\Programs\\PROD\\bcitfm\\api\\request"
    resp_2 = "\\\\bcimcs8.corp.bcimc.com\\sharedir\\TFM\\Programs\\PROD\\bcitfm\\api\\response"
    testServiceObject = TestServiceObject()
    tfmapi = TFMAPI(request_folder=req_2, response_folder=resp_2, service_object=testServiceObject)
    tfmapi.run()
