import watchdog.events
import watchdog.observers
import os, shutil
import json

class MasterRequestHandler(watchdog.events.FileSystemEventHandler):
    """
    Description: Designed to detect request files and move them to their respective venv folder
    Parameters:
        - venv_dedicated_folder_dic: A dictionary containing the venv's request path
    """
    def __init__(self, print_queue, venv_dedicated_folder_dic):
        self.venv_dedicated_folder_dic = venv_dedicated_folder_dic
        self.print_queue = print_queue

    def move_file(self, venv, request_absolute_file_path, filename):
        """
        Description: Moves file from main request folder to venv's request folder
        Parameters:
            - venv: virtual environment
            - request_absolute_file_path: Old request file path
            - filename: request filename
        Return:
        """
        # If venv is recognized, do the following
        if venv in self.venv_dedicated_folder_dic:
            # Get new file path
            venv_request_folder = self.venv_dedicated_folder_dic[venv]
            new_absolute_file_path = f"{venv_request_folder}\\{filename}"
            if os.path.isfile(request_absolute_file_path):
                # Move file to new folder
                shutil.move(request_absolute_file_path, new_absolute_file_path)
                self.print_queue.put(f"Master Watchdog-> Request JSON moved to: {venv}")
            else:
                self.print_queue.put(f"ERROR! The file does exist: '{request_absolute_file_path}'")
        else:
            self.print_queue.put(f"ERROR! The file '{filename}' could not be processed because '{venv}' is not supported")
            if os.path.isfile(request_absolute_file_path):
                os.remove(request_absolute_file_path)
            
    def on_created(self, event):
        """
        Description: Detect created files
        Parameters: None
        Return: None
        """
        try:
            absolute_file_path = os.path.abspath(event.src_path)
            filename = os.path.basename(absolute_file_path)

            # Check if a signal request file is created
            if '.signal' in filename:
                # Get the .json path (same filename as the signal file, only different file extension)
                request_absolute_file_path = absolute_file_path.replace('.signal', '.json')
                if os.path.isfile(request_absolute_file_path):
                    filename = os.path.basename(request_absolute_file_path)

                    # Extract venv from request json
                    file = open(request_absolute_file_path)
                    venv = json.load(file)['venv']
                    file.close()

                    # Move file to respective venv folder
                    self.move_file(venv, request_absolute_file_path, filename)
                
                # Request JSON file doesn't exist
                else: 
                    function_output = f"Master Watchdog -> Error! Request file '{request_absolute_file_path}' does not exist."
                    self.print_queue.put(function_output)

                # remove .signal file
                try:
                    os.remove(absolute_file_path)
                except PermissionError as e:
                    error_string = f"MASTER WATCHDOG EXCEPTION!!!!: {absolute_file_path}; {e}"
                    self.print_queue.put(error_string)
                    

        except Exception as e:
            self.print_queue.put(e)

    def on_deleted(self, event):
        """
        Description: Detect deleted files
        Parameters: None
        Return: None
        """
        try:
            None
            # absolute_file_path = os.path.abspath(event.src_path)
            # self.print_queue.put(f"Master Watchdog -> DELETED: {absolute_file_path}")
        except Exception as e:
            self.print_queue.put(e)

class ChildRequestHandler(watchdog.events.FileSystemEventHandler):
    """
    Description: Designed to detect request files and enqueue them into the task_queue
    Parameters:
        - task_queue: Contains the path of request files ready to be processed
    """
    def __init__(self, task_queue, print_queue):
        self.task_queue = task_queue
        self.print_queue = print_queue

    def on_created(self, event):
        """
        Description: Detect created files
        Parameters: None
        Return: None
        """
        try:
            absolute_file_path = os.path.abspath(event.src_path)
            self.task_queue.put(absolute_file_path)
            self.print_queue.put(f"Child Watchdog -> Received Request: {absolute_file_path}")

        except Exception as e:
            self.print_queue.put(e)

    def on_deleted(self, event):
        """
        Description: Detect deleted files
        Parameters: None
        Return: None
        """
        try:
            None
            # absolute_file_path = os.path.abspath(event.src_path)
            # self.print_queue.put(f"Child Watchdog-> DELETED: {absolute_file_path}")
        except Exception as e:
            self.print_queue.put(e)

class ResponseHandler(watchdog.events.FileSystemEventHandler):
    """
    Description: Designed to detect response files
    Parameters: None
    """
    def __init__(self, print_queue):
        self.print_queue = print_queue

    def on_created(self, event):
        """
        Description: Detect created files
        Parameters: None
        Return: None
        """
        try:
            absolute_file_path = os.path.abspath(event.src_path)
            filename = os.path.basename(absolute_file_path)
            if '.json' in filename:
                self.print_queue.put(f"Master Watchdog -> New Response: {absolute_file_path}")
        except Exception as e:
            self.print_queue.put(e)
    def on_deleted(self, event):
        """
        Description: Detect deleted files
        Parameters: None
        Return: None
        """
        try:
            None
            # absolute_file_path = os.path.abspath(event.src_path)
            # self.print_queue.put(f"Master Watchdog -> DELETED: {absolute_file_path}")
        except Exception as e:
            self.print_queue.put(e)

def create_master_watchdog(print_queue, venv_dedicated_folder_dic, request_path, response_path):
    # Watchdog to observe the main request folder
    event_handler = MasterRequestHandler(print_queue, venv_dedicated_folder_dic)
    observer = watchdog.observers.Observer()
    observer.schedule(event_handler, path=request_path)
    observer.start()

    # Watchdog to observe the response folder
    event_handler = ResponseHandler(print_queue)
    observer = watchdog.observers.Observer()
    observer.schedule(event_handler, path=response_path)
    observer.start()
    print_queue.put("Master Watchdog Ready")

def create_child_watchdog(task_queue, print_queue, request_path):
    # Watchdog to observe the venv request folder
    event_handler = ChildRequestHandler(task_queue, print_queue)
    observer = watchdog.observers.Observer()
    observer.schedule(event_handler, path=request_path)
    observer.start()
    print_queue.put("Child Watchdog Ready")

