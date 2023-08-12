import threading
import time
import asyncio
from enum import Enum
from queue import Queue
import logging
import colorlog
import sys
import os
from datetime import datetime

#
#   User Input
#

class KeyboardThread(threading.Thread):
    """
        Class for asynchronously getting keyboard input from the user
    """

    def __init__(self, callback=None, active=False, name="keyboard-input-thread"):
        self.callback = callback
        self.active = active
        super(KeyboardThread, self).__init__(name=name)
        self.daemon = True
        self.start()
    
    def run(self):
        while True:
            if active:
                self.callback(input())
            else:
                time.sleep(0.1)

#
#   Logging
#

# Formats and colors
LOGFORMAT = "[%(asctime)s] [%(name)s/%(threadName)s/%(levelname)s] %(message)s"
CLOGFORMAT = "[%(asctime)s] %(log_color)s[%(name)s/%(threadName)s/%(levelname)s]%(reset)s %(message_log_color)s%(message)s"
DATEFORMAT = "%H:%M:%S"
LOGCOLORS = {
    "DEBUG":    "white",
    "INFO":     "green",
    "WARNING":  "yellow",
    "ERROR":    "red",
    "CRITICAL": "black,bg_red"
}
SECONDARY_LOG_COLORS = {
    "message": {
        "DEBUG":    "white",
        "INFO":     "light_white",
        "WARNING":  "yellow",
        "ERROR":    "red",
        "CRITICAL": "red"
    }
}

def get_logfile_path(log_path, base_filename=None, ending="log"):
    """
        Returns a path to a new logfile based upon a base {log_path}, a {base_filename} and a file {ending}
    """
    
    # If path is not a directory, raise error
    if not os.path.isdir(log_path):
        raise ValueError("Log Path is not a directory")
    
    datetime_string = datetime.today().strftime("%Y-%m-%d")
    
    base_string=""
    
    # base filename can be None, in which case it is completely omitted
    if not (base_filename is None):
        base_string = f"{base_filename}_"
    
    log_filename= f"{base_string}{datetime_string}"
    
    # If file with name already exists, add increasing integer until free file is found
    i = 1
    logfile_path = os.path.join(log_path, f"{log_filename}.{ending}")
    
    while os.path.exists(logfile_path):
        # Failsave to not create endless loop
        if i > 1000000:
            raise FileExistsError("All log files with added integers up to 1000000 already exist, what are you doing?!")
        
        logfile_path = os.path.join(log_path, f"{log_filename}_{i}.{ending}")
        i += 1

    return logfile_path

def setup_console_logging(log_debug=False):
    """
        Setup (colored) logging formats for console output using the logging module
        
        Arguments:
            - log_debug: Wether to include log messages with level logging.DEBUG
    """
    
    colorformatter = colorlog.ColoredFormatter(CLOGFORMAT, datefmt=DATEFORMAT, log_colors=LOGCOLORS, secondary_log_colors=SECONDARY_LOG_COLORS)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    
    # Initialize handler for standard out (Non-error console)
    out_console = logging.StreamHandler(sys.stdout)
    out_console.setFormatter(colorformatter)
    out_console.setLevel(logging.DEBUG if log_debug else logging.INFO)
    out_console.addFilter(lambda record: record.levelno <= logging.WARNING)
    root_logger.addHandler(out_console)
    
    # Initialize handler for standard error (Error console)
    err_console = logging.StreamHandler(sys.stderr)
    err_console.setFormatter(colorformatter)
    err_console.setLevel(logging.ERROR)
    root_logger.addHandler(err_console)

def setup_file_logging(log_path, log_debug=False):
    """
        Setup logging formats for log file output using the logging module
        
        Arguments:
            - log_path: Path to a directory to store logs at
            - log_debug: Wether to include log messages with level logging.DEBUG
    """
    
    plainformatter = logging.Formatter(LOGFORMAT, datefmt=DATEFORMAT)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
        
    # Create logfile path if not existing yet
    if not os.path.exists(log_path):
        os.makedirs(log_path)
    
    logfile_path = get_logfile_path(log_path, "astrotux")
    
    file_log = logging.FileHandler(logfile_path)
    file_log.setFormatter(plainformatter)
    file_log.setLevel(logging.DEBUG if log_debug else logging.INFO)
    
    root_logger.addHandler(file_log)
    
    return file_log

#
#   Notifications
#

class EventType(Enum):
    MESSAGE = "message"
    START = "start"
    REGISTERED = "registered"
    SHUTDOWN = "shutdown"
    CRASH = "crash"
    PLAYER_JOIN = "player_join"
    PLAYER_LEAVE = "player_leave"
    COMMAND = "command"

class NotificationManager:
    """ Class that keeps multiple Notification Handlers and broadcasts messages to all of them """
    
    def __init__(self):
        self.handlers = []
    
    def add_handler(self, handler):
        """ Add notification handler to manager """
        self.handlers.append(handler)
    
    def clear(self):
        self.handlers.clear()
    
    def send_event(self, event_type=EventType.MESSAGE, **params):
        """ Send event to all registered notification handlers """
        for handler in self.handlers:
            handler.send_event(event_type, **params)

def safeformat(str, **kwargs):
    """
        Formats the passed string {str} using the given keyword arguments, while keeping missing replacements unformatted
    """
    
    class SafeDict(dict):
        def __missing__(self, key):
            return '{' + key + '}'
        
    replacements = SafeDict(**kwargs)
    
    return str.format_map(replacements)

DEFAULT_EVENT_FORMATS = {
        EventType.MESSAGE: "[{name}] {message}",
        EventType.START: "[{name}] Server started!",
        EventType.REGISTERED: "[{name}] Server registered with Playfab!",
        EventType.SHUTDOWN: "[{name}] Server shutdown!",
        EventType.CRASH: "[{name}] Server crashed!",
        EventType.PLAYER_JOIN: "[{name}] Player '{player}' joined the game",
        EventType.PLAYER_LEAVE: "[{name}] Player '{player}' left the game",
        EventType.COMMAND: "[{name}] Command executed: {command}"
    }

class NotificationHandler:
    """
        A class that can receive events and send them along as formatted messages to some endpoint
    """
    
    def __init__(self, name="Server", event_whitelist=set([e for e in EventType]), event_formats=DEFAULT_EVENT_FORMATS):
        self.name = name
        self.whitelist = event_whitelist
        self.formats = event_formats
    
    def send_event(self, event_type=EventType.MESSAGE, **params):
        """ Send event using the provided parameters """
        
        # Only send, if event is in whitelist
        if event_type in self.whitelist:
            # Add server name to parameters for formatting
            params["name"] = self.name
            message = safeformat(self.formats[event_type], **params)
            
            self._send_message(event_type, message)
    
    def _send_message(self, event_type, message):
        """
            Internal method to actually pass the message on.
            To be overwritten by subclasses.
        """
        
        print(message)

class QueuedNotificationHandler(NotificationHandler):
    """
        Notification handler that uses a thread and a queue to handle events asynchronously
    """
    
    class NotificationThread(threading.Thread):
        def __init__(self, callback, name="keyboard-input-thread"):
            self.callback = callback
            self.event_queue = Queue()
            self.wakeup_event = threading.Event()
            
            super(QueuedNotificationHandler.NotificationThread, self).__init__(name=name)
            self.daemon = True
            self.start()
        
        def add_event(self, event_type, message):
            """ Add an event to the internal queue """
            self.event_queue.put((event_type, message))
            self.wakeup_event.set()
        
        def run(self):
            while True:
                if not self.event_queue.empty():
                    # If the queue is not empty, there are events to handle
                    event = self.event_queue.get()
                    self.callback(*event)
                else:
                    # If queue is empty, sleep for 10s or until the wakeup_event is set
                    self.wakeup_event.wait(timeout=10)
                    self.wakeup_event.clear()
    
    def __init__(self, name="Server", event_whitelist=set([e for e in EventType]), event_formats=DEFAULT_EVENT_FORMATS):
        super().__init__(name, event_whitelist, event_formats)
        
        self.thread = QueuedNotificationHandler.NotificationThread(self._handle_message)
    
    def _send_message(self, event_type, message):
        self.thread.add_event(event_type, message)
    
    def _handle_message(self, event_type, message):
        """
            Method for handling events asynchronously.
            To be overritten by subclasses.
        """
        
        time.sleep(3)
        print(message)