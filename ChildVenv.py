import os, sys
import json
import multiprocessing, threading
import handler
import importlib
import time, datetime
import socket
import Protocol


def process_json_request(self, request_absolute_file_path):
    function_output = ''
    error_flag = False
    json_content = {}
    if os.path.isfile(request_absolute_file_path):
        try:
            start_time = time.time()
            while not os.access(request_absolute_file_path, os.R_OK):
                # Wait to have access to the file
                if (time.time() - start_time) > 2:
                    # TIMEOUT after 2 second
                    raise Exception("Unable to access file as it's being accessed by another program. File path: {request_absolute_file_path}")

            try:
                with open(request_absolute_file_path, 'r') as file:
                    json_content = json.load(file)
            except Exception as e:
                time.sleep(0.5)
                # try again
                with open(request_absolute_file_path, 'r') as file:
                    json_content = json.load(file)
                
        except Exception as e:
            function_output = f"Error code 1! Couldn't open file. {e}"
            error_flag = True
            self.error_queue.put(function_output)
            raise Exception(e)

        # Update any module changes and don't rely on cache
        importlib.invalidate_caches()
        module_absolute_path = json_content['module_absolute_path']
        # Check if module file exists
        try:
            if not error_flag:
                if os.path.isfile(module_absolute_path):
                    module_filename = os.path.basename(module_absolute_path)
                    imported_module = importlib.machinery.SourceFileLoader(module_filename, module_absolute_path).load_module()
                    if json_content['function'] in imported_module.__dict__:
                        function_output = imported_module.__dict__[json_content['function']](*json_content['parameters'])
                    else:
                        function_output = f"Error code 2! The function '{json_content['function']}' does not exist in Module '{module_filename}'. "
                        error_flag = True
                        self.error_queue.put(function_output)
                else:
                    function_output = f"{Protocol.MODULE_DOES_NOT_EXIST}| Module '{os.path.basename(module_absolute_path)}' does not exist."
                    error_flag = True
                    self.error_queue.put(function_output)
        except Exception as e:
            function_output = f"Exception Raised in Requested Module/Function|{e}"
            error_flag = True
            self.error_queue.put(function_output)
            
    else:
        function_output = f"Error code 4! Request file '{request_absolute_file_path}' does not exist."
        error_flag = True
        self.error_queue.put(function_output)

    json_output = {
        "venv": json_content['venv'],
        "function_output": function_output,
        "error": error_flag
    }
    
    return json_output

def module_process(self, testing=False):
    """
    Description:
        While looping infinitely, pop available tasks from the queue, process the request json, then output the result in a response json

    Parameters:
        - task_queue: A thread-safe queue shared across all instances of module_process
        - response_folder_path: Path which specifies where to create the response json
        - venv: Virtual environment which the parent process is currently running in

    Return: None

    Note:
        - This process will not terminate unless an unexpected error is encountered
    """
    try:
        while not testing:
                
            # Wait for a new task. (self.task_queue.get() is a blocking function call)
            request_absolute_file_path = self.task_queue.get()
            request_filename = os.path.basename(request_absolute_file_path)
            self.print_queue.put(f"POPPED FROM QUEUE: {request_filename}")

            # Go through the json
            json_output = process_json_request(self, request_absolute_file_path)

            # Create response JSON file
            with open(self.response_folder_path + "\\" + request_filename, "w") as outfile:
                json.dump(json_output, outfile)

            # Create signal file
            request_filename = request_filename.replace('.json', '.signal')
            open(self.response_folder_path + "\\" + request_filename, 'a').close()

            os.remove(request_absolute_file_path)

    except Exception as e:
        self.error_queue.put(e)
        self.process_exception_handling.put("Exit")


class ChildVenv:
    
    def __init__(self, venv, request_folder_path, response_folder_path, connection_port):
        self.venv = venv
        self.request_folder_path = request_folder_path
        self.response_folder_path = response_folder_path
        self.stop_requested = False
        self.connection_port = int(connection_port)
        self.log_directory = "\\\\bcimcs8.corp.bcimc.com\\sharedir\\TFM\\Programs\\PROD\\bcitfm\\api\\logs\\ChildVenvLog.txt"
        self.task_queue = multiprocessing.Queue()
        self.print_queue = multiprocessing.Queue()
        self.error_queue = multiprocessing.Queue()
        self.process_exception_handling = multiprocessing.Queue() # Bad and unoptimized solution. Find better exception handling

    def initialize_run(self):
        self.initiate_connection()
        if self.sock is None:
            # Exit process
            exit(2)

        logger_thread = threading.Thread(target= self.log_thread, daemon=True)
        logger_thread.start()
        handler.create_child_watchdog(self.task_queue, self.print_queue, self.request_folder_path)
        manager_thread = threading.Thread(target= self.processes_manager, daemon=True)
        manager_thread.start()
        # manager_thread = threading.Thread(target= self.module_process, daemon=True)
        # manager_thread.start()

    def processes_manager(self):
        """
        Description:
        Step 1) Create n processes which will run the requested modules where n = multiprocessing.cpu_count()/2
        Step 2) Start the processes
        Step 3) Wait until the processes terminate

        Notes:
            - Processes will not terminate unless an unexpected error is encountered

        Parameters: None
        Return: None	
        """
        max_process_count = int(multiprocessing.cpu_count()/2)
        process_list = []
        for i in range(0, max_process_count):
            process = multiprocessing.Process(target= module_process, args=(self,))
            process.start()
            process_list.append(process)
        
        self.print_queue.put(f"Child: {self.venv} is ready")
        
        # for p in process_list:
        #     p.join()

        # This should stay blocked unless a process fails
        tmp = self.process_exception_handling.get()

        self.error_queue.put(f"Error!: Processing manager exiting")
        self.stop_requested = True

    def log_thread(self):
        while True:
            if not self.print_queue.empty():
                print_message = self.print_queue.get()
                if print_message == Protocol.TEST_CONNECTION:
                    response_packet = f"{Protocol.TEST_CONNECTION}"
                    self.sock.send(response_packet.encode())
                else:
                    response_packet = f"{Protocol.DATA}|{print_message}"
                    self.sock.send(response_packet.encode())
                    local_log2(response_packet)

            if not self.error_queue.empty():
                response_packet = f"{Protocol.ERROR}|{self.error_queue.get()}"
                self.sock.send(response_packet.encode())
                local_log2(response_packet)
            
    def initiate_connection(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("localhost", self.connection_port))
        # Get init
        data_packet = sock.recv(1024).decode()
        if Protocol.INITIALIZE in data_packet:
            # Send venv
            response_packet = f"{Protocol.VENV}|{self.venv}"
            sock.send(response_packet.encode())
        else:
            # Send response again
            self.stop_requested = True
        # Get approval
        data_packet = sock.recv(1024).decode()
        if not Protocol.APPROVE in data_packet:
            # Close connection
            self.stop_requested = True
        # Store socket locally
        self.sock = sock
        
    def local_log(self, string):
        with open(self.log_directory, 'a') as myfile:
            current_datetime = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            output_string = f"{current_datetime} | {string}\n"
            myfile.write(output_string)

    def run(self):
        self.initialize_run()
        connection_check_time = time.time()
        while not self.stop_requested:
            if (time.time() - connection_check_time) > 20:
                self.print_queue.put(Protocol.TEST_CONNECTION)
                connection_check_time = time.time()
            time.sleep(2)

# Used for testing purposes
def local_log2(string):
    with open("\\\\bcimcs8.corp.bcimc.com\\sharedir\\TFM\\Programs\\PROD\\bcitfm\\api\\logs\\ChildVenvLog.txt", 'a') as myfile:
        current_datetime = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        output_string = f"{current_datetime} | {string}\n"
        myfile.write(output_string)

if __name__ == "__main__":
    try:
        input_argv = sys.argv
        venv = input_argv[1]
        local_log2(f"{venv}, {os.path.dirname(sys.executable)}")
        request_folder_path = input_argv[2]
        response_folder_path = input_argv[3]
        connection_port = input_argv[4]
        childVenv = ChildVenv(venv, request_folder_path, response_folder_path, connection_port)
        childVenv.run()
    except Exception as e:
        local_log2("Fatal Eception")
        local_log2(e)
    local_log2("EXITING")
    exit(-2)
