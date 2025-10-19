import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox, filedialog
import threading
import json
import os
import hashlib
import uuid
from datetime import datetime
from paho.mqtt import client as mqtt
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import socketserver

class TemplateHTTPHandler(BaseHTTPRequestHandler):
    """HTTP handler for template file serving"""
    
    def __init__(self, *args, template_manager=None, **kwargs):
        self.template_manager = template_manager
        super().__init__(*args, **kwargs)
    
    def do_POST(self):
        """Handle POST requests for template loading"""
        try:
            # Log the request with detailed headers
            self.log_message("=== POST REQUEST DEBUG ===")
            self.log_message("Client: %s:%s", self.client_address[0], self.client_address[1])
            self.log_message("Path: %s", self.path)
            self.log_message("Headers: %s", dict(self.headers))
            
            # Get content length
            content_length = int(self.headers.get('Content-Length', 0))
            self.log_message("Content-Length header: %d", content_length)
            
            # Read the request body
            if content_length == 0:
                self.log_message("ERROR: Empty request body (Content-Length = 0)")
                self.send_error(400, "Empty request body")
                return
                
            # Read data in chunks to handle potential network issues
            post_data = b''
            bytes_read = 0
            while bytes_read < content_length:
                chunk = self.rfile.read(min(1024, content_length - bytes_read))
                if not chunk:
                    self.log_message("WARNING: Connection closed before all data received")
                    break
                post_data += chunk
                bytes_read += len(chunk)
            
            # Log detailed data information
            self.log_message("Bytes expected: %d, Bytes received: %d", content_length, len(post_data))
            self.log_message("Raw POST data (hex): %s", post_data.hex())
            self.log_message("Raw POST data (repr): %r", post_data)
            
            # Check if we received all expected data
            if len(post_data) != content_length:
                self.log_message("ERROR: Data length mismatch - expected %d, got %d", content_length, len(post_data))
                self.send_error(400, f"Data length mismatch: expected {content_length}, got {len(post_data)}")
                return
            
            # Decode and parse JSON
            try:
                data_str = post_data.decode('utf-8')
                self.log_message("Decoded UTF-8 string: %r", data_str)
                
                # Check for common issues
                if not data_str.strip():
                    self.log_message("ERROR: Decoded string is empty or whitespace only")
                    self.send_error(400, "Empty JSON data")
                    return
                
                # Fix common JSON format issues
                original_data_str = data_str
                data_str = data_str.strip()
                
                # Remove outer single quotes if present
                if data_str.startswith("'") and data_str.endswith("'"):
                    data_str = data_str[1:-1]
                    self.log_message("Removed outer single quotes: %r", data_str)
                
                # Fix missing quotes around keys and values (common curl mistake)
                import re
                # Replace {key: with {"key":
                data_str = re.sub(r'\{(\w+):', r'{"\1":', data_str)
                # Replace ,key: with ,"key":
                data_str = re.sub(r',(\w+):', r',"\1":', data_str)
                # Replace :value} with :"value"} for unquoted string values
                # This regex looks for :word} or :word, patterns and adds quotes
                data_str = re.sub(r':([^",\{\}\[\]]+)([,\}])', r':"\1"\2', data_str)
                
                if data_str != original_data_str.strip():
                    self.log_message("Fixed JSON format: %r", data_str)
                    
                data = json.loads(data_str)
                self.log_message("Parsed JSON successfully: %s", data)
                
            except UnicodeDecodeError as e:
                self.log_message("Unicode decode error: %s", str(e))
                self.log_message("Problematic bytes: %r", post_data)
                self.send_error(400, f"Unicode decode error: {str(e)}")
                return
            except json.JSONDecodeError as e:
                self.log_message("JSON decode error: %s", str(e))
                self.log_message("Problematic string: %r", data_str if 'data_str' in locals() else 'N/A')
                self.send_error(400, f"Invalid JSON: {str(e)}")
                return
            
            # Handle template loading request
            if self.path == '/api/res/templ/loadtemple':
                name = data.get('name')
                template_id = data.get('id')
                
                self.log_message("Template request - name: %s, id: %s", name, template_id)
                
                if not name and not template_id:
                    self.send_error(400, "Missing 'name' or 'id' parameter")
                    return
                
                # Find template file
                template_path = self.template_manager.find_template(name=name, template_id=template_id)
                
                if not template_path:
                    self.log_message("Template not found: name=%s, id=%s", name, template_id)
                    self.send_error(404, f"Template not found: {name or template_id}")
                    return
                
                # Read and send template file
                try:
                    with open(template_path, 'rb') as f:
                        content = f.read()
                    
                    # Get filename for Content-Disposition header
                    filename = os.path.basename(template_path)
                    
                    # Handle filename encoding for HTTP headers
                    try:
                        # Try ASCII encoding first
                        filename.encode('ascii')
                        disposition = f'attachment; filename="{filename}"'
                    except UnicodeEncodeError:
                        # Use RFC 5987 encoding for non-ASCII filenames
                        from urllib.parse import quote
                        encoded_filename = quote(filename, safe='')
                        disposition = f"attachment; filename*=UTF-8''{encoded_filename}"
                    
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Content-Disposition', disposition)
                    self.send_header('Content-Length', str(len(content)))
                    # Add CORS headers
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                    self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                    self.end_headers()
                    
                    self.wfile.write(content)
                    
                    self.log_message("Template sent successfully: %s", filename)
                    
                except Exception as e:
                    self.log_message("Error reading template file: %s", str(e))
                    self.send_error(500, f"Error reading template file: {str(e)}")
                    return
            else:
                self.send_error(404, "Endpoint not found")
                
        except Exception as e:
            self.log_message("Unexpected error in do_POST: %s", str(e))
            self.send_error(500, f"Internal server error: {str(e)}")
            return
    
    def do_OPTIONS(self):
        """Handle OPTIONS requests for CORS preflight"""
        self.log_message("OPTIONS request received from %s for path %s", self.client_address[0], self.path)
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Content-Length')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_GET(self):
        """Handle GET requests for template listing"""
        self.log_message("GET request received from %s for path %s", self.client_address[0], self.path)
        
        if self.path == '/api/res/templ/list':
            try:
                templates = self.template_manager.get_template_list()
                response_data = json.dumps(templates, indent=2)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(response_data)))
                self.end_headers()
                self.wfile.write(response_data.encode('utf-8'))
                
            except Exception as e:
                self.send_error(500, f"Internal server error: {str(e)}")
        elif self.path == '/api/health':
            # Health check endpoint
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            response = json.dumps({"status": "ok", "message": "Server is running"})
            self.wfile.write(response.encode('utf-8'))
        else:
            self.send_error(404, "Endpoint not found")
    
    def log_message(self, format, *args):
        """Override to enable logging for debugging"""
        message = format % args
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] HTTP: {message}")
        # Also log to template manager if available
        if self.template_manager and hasattr(self.template_manager, 'log_request'):
            self.template_manager.log_request(message)

class TemplateManager:
    """Template file management system"""
    
    def __init__(self, resource_dir, logger=None):
        self.resource_dir = resource_dir
        self.logger = logger
        self.templates = {}
        self.ensure_resource_dir()
        self.scan_templates()
    
    def ensure_resource_dir(self):
        """Ensure resource directory exists"""
        if not os.path.exists(self.resource_dir):
            os.makedirs(self.resource_dir)
    
    def scan_templates(self):
        """Scan resource directory for template files"""
        self.templates.clear()
        if not os.path.exists(self.resource_dir):
            return
        
        for filename in os.listdir(self.resource_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(self.resource_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        template_data = json.load(f)
                    
                    # Generate MD5 hash
                    with open(filepath, 'rb') as f:
                        md5_hash = hashlib.md5(f.read()).hexdigest()
                    
                    # Extract template info
                    template_name = template_data.get('Name', filename.replace('.json', ''))
                    template_id = str(uuid.uuid4())  # Generate unique ID
                    
                    self.templates[filename] = {
                        'name': template_name,
                        'id': template_id,
                        'filename': filename,
                        'filepath': filepath,
                        'md5': md5_hash,
                        'size': os.path.getsize(filepath),
                        'modified': datetime.fromtimestamp(os.path.getmtime(filepath)).isoformat()
                    }
                except Exception as e:
                    if self.logger:
                        self.logger(f"Error scanning template {filename}: {str(e)}", "ERROR")
    
    def add_template(self, source_file):
        """Add a new template file"""
        try:
            filename = os.path.basename(source_file)
            dest_path = os.path.join(self.resource_dir, filename)
            
            # Copy file to resource directory
            with open(source_file, 'rb') as src, open(dest_path, 'wb') as dst:
                dst.write(src.read())
            
            # Rescan templates
            self.scan_templates()
            
            if self.logger:
                self.logger(f"Template added: {filename}", "SUCCESS")
            
            return True
        except Exception as e:
            if self.logger:
                self.logger(f"Failed to add template: {str(e)}", "ERROR")
            return False
    
    def remove_template(self, filename):
        """Remove a template file"""
        try:
            filepath = os.path.join(self.resource_dir, filename)
            if os.path.exists(filepath):
                os.remove(filepath)
                self.scan_templates()
                
                if self.logger:
                    self.logger(f"Template removed: {filename}", "SUCCESS")
                return True
            return False
        except Exception as e:
            if self.logger:
                self.logger(f"Failed to remove template: {str(e)}", "ERROR")
            return False
    
    def find_template(self, name=None, template_id=None):
        """Find template file by name or ID"""
        for filename, info in self.templates.items():
            if name:
                # Try exact match first
                if info['name'] == name or filename == name:
                    return info['filepath']
                # Try partial match (without .json extension)
                if filename.replace('.json', '') == name:
                    return info['filepath']
                # Try fuzzy match (contains the name)
                if name in filename or name in info['name']:
                    return info['filepath']
            if template_id and info['id'] == template_id:
                return info['filepath']
        return None
    
    def get_template_list(self):
        """Get list of all templates"""
        return list(self.templates.values())
    
    def log_request(self, message):
        """Log HTTP requests"""
        if self.logger:
            self.logger(message, "HTTP")

class MQTTApp:
    def __init__(self, root):
        self.root = root
        self.client = None
        self.is_connected = False
        self.http_server = None
        self.http_thread = None
        
        # Initialize template manager first
        self.resource_dir = os.path.join(os.path.dirname(__file__), 'resource')
        self.template_manager = TemplateManager(self.resource_dir, self.log_msg)
        
        # Setup UI after template manager is ready
        self.setup_ui()
        
        # Start HTTP server
        self.start_http_server()
        
    def setup_ui(self):
        """Initialize and configure the user interface"""
        self.root.title("MQTT Template Server")
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')
        
        # Configure styles
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure custom styles
        style.configure('Title.TLabel', font=('Arial', 12, 'bold'), background='#f0f0f0')
        style.configure('Connect.TButton', font=('Arial', 10, 'bold'))
        style.configure('Action.TButton', font=('Arial', 9))
        
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights for responsive design
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=2)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(3, weight=1)
        
        # Left side - MQTT functionality
        left_frame = ttk.Frame(main_frame)
        left_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=(0, 10))
        left_frame.columnconfigure(1, weight=1)
        left_frame.rowconfigure(3, weight=1)
        
        # Connection Section
        conn_frame = ttk.LabelFrame(left_frame, text="MQTT Connection Settings", padding="15")
        conn_frame.grid(row=0, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        conn_frame.columnconfigure(1, weight=1)
        
        ttk.Label(conn_frame, text="Broker IP:", style='Title.TLabel').grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.ip = ttk.Entry(conn_frame, font=('Arial', 10), width=20)
        self.ip.insert(0, "127.0.0.1")
        self.ip.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 20))

        ttk.Label(conn_frame, text="Port:", style='Title.TLabel').grid(row=0, column=2, sticky='w', padx=(0, 10))
        self.port = ttk.Entry(conn_frame, font=('Arial', 10), width=10)
        self.port.insert(0, "1883")
        self.port.grid(row=0, column=3, sticky='w')

        ttk.Label(conn_frame, text="Username:", style='Title.TLabel').grid(row=1, column=0, sticky='w', padx=(0, 10), pady=(10, 0))
        self.username = ttk.Entry(conn_frame, font=('Arial', 10))
        self.username.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(0, 20), pady=(10, 0))

        ttk.Label(conn_frame, text="Password:", style='Title.TLabel').grid(row=1, column=2, sticky='w', padx=(0, 10), pady=(10, 0))
        self.password = ttk.Entry(conn_frame, show="*", font=('Arial', 10))
        self.password.grid(row=1, column=3, sticky='w', pady=(10, 0))

        # Connection button with status indicator
        button_frame = ttk.Frame(conn_frame)
        button_frame.grid(row=2, column=0, columnspan=4, pady=(15, 0))
        
        self.connect_btn = ttk.Button(button_frame, text="Connect", command=self.connect, style='Connect.TButton')
        self.connect_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.status_label = ttk.Label(button_frame, text="Disconnected", foreground='red')
        self.status_label.pack(side=tk.LEFT)

        # Subscribe Section
        sub_frame = ttk.LabelFrame(left_frame, text="Subscribe to Topic", padding="15")
        sub_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        sub_frame.columnconfigure(0, weight=1)

        topic_sub_frame = ttk.Frame(sub_frame)
        topic_sub_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        topic_sub_frame.columnconfigure(0, weight=1)

        ttk.Label(topic_sub_frame, text="Topic:", style='Title.TLabel').grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.topic_sub = ttk.Entry(topic_sub_frame, font=('Arial', 10))
        self.topic_sub.insert(0, "template/request")
        self.topic_sub.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        self.topic_sub.bind('<Return>', lambda e: self.subscribe())
        
        ttk.Button(topic_sub_frame, text="Subscribe", command=self.subscribe, style='Action.TButton').grid(row=0, column=2)

        # Publish Section
        pub_frame = ttk.LabelFrame(left_frame, text="Publish Message", padding="15")
        pub_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        pub_frame.columnconfigure(0, weight=1)

        ttk.Label(pub_frame, text="Topic:", style='Title.TLabel').grid(row=0, column=0, sticky='w', pady=(0, 5))
        self.topic_pub = ttk.Entry(pub_frame, font=('Arial', 10))
        self.topic_pub.insert(0, "template/response")
        self.topic_pub.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(pub_frame, text="Message (JSON):", style='Title.TLabel').grid(row=1, column=0, sticky='nw', pady=(0, 5))
        
        # Message text area with better styling
        msg_frame = ttk.Frame(pub_frame)
        msg_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        msg_frame.columnconfigure(0, weight=1)
        
        self.message = scrolledtext.ScrolledText(msg_frame, width=40, height=4, font=('Consolas', 10), 
                                               wrap=tk.WORD, relief='solid', borderwidth=1)
        self.message.grid(row=0, column=0, sticky=(tk.W, tk.E))

        publish_frame = ttk.Frame(pub_frame)
        publish_frame.grid(row=2, column=1, sticky='w')
        ttk.Button(publish_frame, text="Publish", command=self.publish, style='Action.TButton').pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(publish_frame, text="Clear", command=self.clear_message, style='Action.TButton').pack(side=tk.LEFT)

        # Log Section
        log_frame = ttk.LabelFrame(left_frame, text="Activity Log", padding="15")
        log_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log = scrolledtext.ScrolledText(log_frame, width=60, height=10, state='disabled', 
                                           font=('Consolas', 9), wrap=tk.WORD, relief='solid', borderwidth=1)
        self.log.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure text tags for different message alignments and colors
        self.log.tag_configure("sent", justify='right', foreground='#0066cc', background='#e6f3ff')
        self.log.tag_configure("received", justify='left', foreground='#009900', background='#f0fff0')
        self.log.tag_configure("info", justify='center', foreground='#666666')
        self.log.tag_configure("error", justify='center', foreground='#cc0000', background='#ffe6e6')
        self.log.tag_configure("success", justify='center', foreground='#009900', background='#f0fff0')
        self.log.tag_configure("warning", justify='center', foreground='#ff6600', background='#fff3e6')
        self.log.tag_configure("http", justify='center', foreground='#9900cc', background='#f9f0ff')
        
        # Add clear log button
        ttk.Button(log_frame, text="Clear Log", command=self.clear_log, style='Action.TButton').grid(row=1, column=0, sticky='w', pady=(10, 0))

        # Right side - Template Management
        right_frame = ttk.LabelFrame(main_frame, text="Template File Manager", padding="15")
        right_frame.grid(row=0, column=1, rowspan=4, sticky=(tk.W, tk.E, tk.N, tk.S))
        right_frame.columnconfigure(0, weight=1)
        right_frame.rowconfigure(1, weight=1)
        
        # Template management buttons
        template_btn_frame = ttk.Frame(right_frame)
        template_btn_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 10))
        
        ttk.Button(template_btn_frame, text="Add Template", command=self.add_template, style='Action.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(template_btn_frame, text="Remove Selected", command=self.remove_template, style='Action.TButton').pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(template_btn_frame, text="Refresh", command=self.refresh_templates, style='Action.TButton').pack(side=tk.LEFT)
        
        # Template list
        list_frame = ttk.Frame(right_frame)
        list_frame.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        # Create treeview for template list
        columns = ('Name', 'Size', 'Modified')
        self.template_tree = ttk.Treeview(list_frame, columns=columns, show='tree headings', height=15)
        
        # Configure columns
        self.template_tree.heading('#0', text='Filename')
        self.template_tree.heading('Name', text='Template Name')
        self.template_tree.heading('Size', text='Size')
        self.template_tree.heading('Modified', text='Modified')
        
        self.template_tree.column('#0', width=150)
        self.template_tree.column('Name', width=120)
        self.template_tree.column('Size', width=80)
        self.template_tree.column('Modified', width=120)
        
        # Add scrollbar
        tree_scroll = ttk.Scrollbar(list_frame, orient='vertical', command=self.template_tree.yview)
        self.template_tree.configure(yscrollcommand=tree_scroll.set)
        
        self.template_tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        tree_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        
        # Server info
        server_info_frame = ttk.LabelFrame(right_frame, text="HTTP Server Info", padding="10")
        server_info_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=(10, 0))
        
        self.server_info = ttk.Label(server_info_frame, text="Server: http://10.3.36.36:8080", font=('Arial', 10, 'bold'))
        self.server_info.pack()
        
        ttk.Label(server_info_frame, text="Endpoints:", font=('Arial', 9, 'bold')).pack(anchor='w')
        ttk.Label(server_info_frame, text="POST /api/res/templ/loadtemple", font=('Consolas', 8)).pack(anchor='w')
        ttk.Label(server_info_frame, text="GET /api/res/templ/list", font=('Consolas', 8)).pack(anchor='w')
        
        # Load initial templates
        self.refresh_templates()

    def start_http_server(self):
        """Start HTTP server for template serving"""
        try:
            def handler(*args, **kwargs):
                return TemplateHTTPHandler(*args, template_manager=self.template_manager, **kwargs)
            
            # Create a custom HTTPServer class to handle potential network issues
            class RobustHTTPServer(HTTPServer):
                def __init__(self, server_address, RequestHandlerClass, bind_and_activate=True):
                    super().__init__(server_address, RequestHandlerClass, bind_and_activate)
                    # Set socket options for better network compatibility
                    import socket
                    self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    # Increase buffer sizes for better network performance
                    self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
                    self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
            
            # Bind to all interfaces (0.0.0.0) to allow access from any IP
            self.http_server = RobustHTTPServer(('0.0.0.0', 8080), handler)
            self.http_thread = threading.Thread(target=self.http_server.serve_forever, daemon=True)
            self.http_thread.start()
            
            # Get local IP for display
            import socket
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            
            self.log_msg(f"HTTP Server started successfully!", "SUCCESS")
            self.log_msg(f"Local access: http://localhost:8080", "INFO")
            self.log_msg(f"Network access: http://{local_ip}:8080", "INFO")
            self.log_msg(f"Available endpoints:", "INFO")
            self.log_msg(f"  POST /api/res/templ/loadtemple - Load template", "INFO")
            self.log_msg(f"  GET /api/res/templ/list - List templates", "INFO")
            self.log_msg(f"  GET /api/health - Health check", "INFO")
            
        except Exception as e:
            self.log_msg(f"Failed to start HTTP server: {str(e)}", "ERROR")

    def add_template(self):
        """Add a new template file"""
        file_path = filedialog.askopenfilename(
            title="Select Template File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if file_path:
            if self.template_manager.add_template(file_path):
                self.refresh_templates()
            else:
                messagebox.showerror("Error", "Failed to add template file")

    def remove_template(self):
        """Remove selected template"""
        selection = self.template_tree.selection()
        if not selection:
            messagebox.showwarning("Warning", "Please select a template to remove")
            return
        
        item = selection[0]
        filename = self.template_tree.item(item)['text']
        
        if messagebox.askyesno("Confirm", f"Remove template '{filename}'?"):
            if self.template_manager.remove_template(filename):
                self.refresh_templates()
            else:
                messagebox.showerror("Error", "Failed to remove template file")

    def refresh_templates(self):
        """Refresh template list display"""
        # Clear existing items
        for item in self.template_tree.get_children():
            self.template_tree.delete(item)
        
        # Rescan templates
        self.template_manager.scan_templates()
        
        # Add templates to tree
        for filename, info in self.template_manager.templates.items():
            size_str = f"{info['size']} bytes"
            modified_str = info['modified'][:19].replace('T', ' ')
            
            self.template_tree.insert('', 'end', text=filename, values=(
                info['name'], size_str, modified_str
            ))

    def log_msg(self, msg, level='INFO'):
        """Add message to log with timestamp and level, with alignment based on message type"""
        timestamp = time.strftime("%H:%M:%S")
        
        # Determine tag based on level
        tag_map = {
            'SENT': 'sent',
            'RECEIVED': 'received', 
            'SUCCESS': 'success',
            'ERROR': 'error',
            'WARNING': 'warning',
            'INFO': 'info',
            'HTTP': 'http'
        }
        tag = tag_map.get(level, 'info')
        
        # Format message based on type
        if level == 'SENT':
            formatted_msg = f"[{timestamp}] {msg} ➤\n"
        elif level == 'RECEIVED':
            formatted_msg = f"◀ [{timestamp}] {msg}\n"
        else:
            formatted_msg = f"[{timestamp}] {level}: {msg}\n"
        
        self.log.config(state='normal')
        
        # Insert message with appropriate tag
        start_pos = self.log.index(tk.END + "-1c")
        self.log.insert(tk.END, formatted_msg)
        end_pos = self.log.index(tk.END + "-1c")
        self.log.tag_add(tag, start_pos, end_pos)
        
        self.log.see(tk.END)
        self.log.config(state='disabled')

    def clear_log(self):
        """Clear the activity log"""
        self.log.config(state='normal')
        self.log.delete('1.0', tk.END)
        self.log.config(state='disabled')

    def clear_message(self):
        """Clear the message text area"""
        self.message.delete('1.0', tk.END)

    def update_connection_status(self, connected):
        """Update UI connection status"""
        self.is_connected = connected
        if connected:
            self.status_label.config(text="Connected", foreground='green')
            self.connect_btn.config(text="Disconnect", command=self.disconnect)
        else:
            self.status_label.config(text="Disconnected", foreground='red')
            self.connect_btn.config(text="Connect", command=self.connect)

    def connect(self):
        """Connect to MQTT broker with improved error handling"""
        if self.is_connected:
            return
            
        def run():
            try:
                self.log_msg("Attempting to connect to MQTT broker...")
                
                # Create client with clean session for faster connection
                self.client = mqtt.Client(clean_session=True)
                
                # Set connection timeout for faster failure detection
                self.client.connect_timeout = 5
                
                if self.username.get().strip():
                    self.client.username_pw_set(self.username.get(), self.password.get())
                
                # Set up callbacks
                self.client.on_connect = self.on_connect
                self.client.on_message = self.on_message
                self.client.on_disconnect = self.on_disconnect
                
                # Connect to broker
                self.client.connect(self.ip.get(), int(self.port.get()), 60)
                self.client.loop_start()
                
            except Exception as e:
                self.log_msg(f"Connection failed: {str(e)}", "ERROR")
                self.root.after(0, lambda: self.update_connection_status(False))

        # Use daemon thread for non-blocking connection
        threading.Thread(target=run, daemon=True).start()

    def disconnect(self):
        """Disconnect from MQTT broker"""
        if self.client and self.is_connected:
            self.client.loop_stop()
            self.client.disconnect()
            self.log_msg("Disconnected from broker")

    def on_connect(self, client, userdata, flags, rc):
        """Callback for successful connection"""
        if rc == 0:
            self.log_msg("Successfully connected to MQTT broker", "SUCCESS")
            self.root.after(0, lambda: self.update_connection_status(True))
        else:
            error_msg = f"Connection failed with code {rc}"
            self.log_msg(error_msg, "ERROR")
            self.root.after(0, lambda: self.update_connection_status(False))

    def on_message(self, client, userdata, msg):
        """Callback for received messages with template request handling"""
        try:
            payload = msg.payload.decode('utf-8')
            self.log_msg(f"Received from [{msg.topic}]: {payload}", "RECEIVED")
            
            # Try to parse as JSON for template requests
            try:
                message_data = json.loads(payload)
                
                # Check if this is a template list request
                if message_data.get('command') == 'tmpllist':
                    self.handle_template_request(message_data)
                    
            except json.JSONDecodeError:
                # Not JSON, just log as regular message
                pass
                
        except UnicodeDecodeError:
            self.log_msg(f"Received binary data from [{msg.topic}]", "RECEIVED")

    def handle_template_request(self, request_data):
        """Handle template list requests from MQTT"""
        try:
            shop = request_data.get('shop', '')
            data = request_data.get('data', {})
            templates_requested = data.get('tmpls', [])
            url = data.get('url', '')
            tid = data.get('tid', '')
            
            self.log_msg(f"Template request from shop {shop} for {len(templates_requested)} templates", "INFO")
            
            # Prepare response with available templates
            available_templates = []
            for template_req in templates_requested:
                template_name = template_req.get('name', '')
                template_id = template_req.get('id', '')
                
                # Find matching template
                template_file = self.template_manager.find_template(template_name, template_id)
                if template_file:
                    # Calculate MD5
                    with open(template_file, 'rb') as f:
                        md5_hash = hashlib.md5(f.read()).hexdigest()
                    
                    available_templates.append({
                        'name': template_name,
                        'id': template_id,
                        'md5': md5_hash,
                        'status': 'available'
                    })
                else:
                    available_templates.append({
                        'name': template_name,
                        'id': template_id,
                        'status': 'not_found'
                    })
            
            # Send response
            response = {
                'shop': shop,
                'data': {
                    'tmpls': available_templates,
                    'url': 'http://10.3.36.36:8080/api/res/templ/loadtemple',
                    'tid': tid
                },
                'id': str(uuid.uuid4()),
                'command': 'tmpllist_response',
                'timestamp': time.time()
            }
            
            # Publish response
            response_topic = self.topic_pub.get() or 'template/response'
            self.client.publish(response_topic, json.dumps(response, indent=2))
            self.log_msg(f"Template list response sent to {response_topic}", "SENT")
            
        except Exception as e:
            self.log_msg(f"Error handling template request: {str(e)}", "ERROR")

    def on_disconnect(self, client, userdata, rc):
        """Callback for disconnection"""
        self.log_msg("Disconnected from broker", "INFO")
        self.root.after(0, lambda: self.update_connection_status(False))

    def subscribe(self):
        """Subscribe to a topic"""
        if not self.client or not self.is_connected:
            self.log_msg("Not connected to broker", "WARNING")
            return
            
        topic = self.topic_sub.get().strip()
        if topic:
            try:
                self.client.subscribe(topic)
                self.log_msg(f"Subscribed to topic: {topic}", "SUCCESS")
            except Exception as e:
                self.log_msg(f"Subscription failed: {str(e)}", "ERROR")
        else:
            self.log_msg("Please enter a topic to subscribe", "WARNING")

    def publish(self):
        """Publish a message to a topic"""
        if not self.client or not self.is_connected:
            self.log_msg("Not connected to broker", "WARNING")
            return
            
        topic = self.topic_pub.get().strip()
        msg = self.message.get("1.0", tk.END).strip()
        
        if not topic:
            self.log_msg("Please enter a topic to publish", "WARNING")
            return
            
        if not msg:
            self.log_msg("Please enter a message to publish", "WARNING")
            return
            
        try:
            self.client.publish(topic, msg)
            self.log_msg(f"Published to [{topic}]: {msg}", "SENT")
        except Exception as e:
            self.log_msg(f"Publish failed: {str(e)}", "ERROR")

    def __del__(self):
        """Cleanup when application closes"""
        if self.http_server:
            self.http_server.shutdown()

if __name__ == "__main__":
    root = tk.Tk()
    app = MQTTApp(root)
    
    def on_closing():
        if app.http_server:
            app.http_server.shutdown()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()