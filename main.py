import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import json
from paho.mqtt import client as mqtt
import time

class MQTTApp:
    def __init__(self, root):
        self.root = root
        self.setup_ui()
        self.client = None
        self.is_connected = False
        
    def setup_ui(self):
        """Initialize and configure the user interface"""
        self.root.title("MQTT Client Tool")
        self.root.geometry("800x700")
        self.root.configure(bg='#f0f0f0')
        
        # Configure styles
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure custom styles
        style.configure('Title.TLabel', font=('Arial', 12, 'bold'), background='#f0f0f0')
        style.configure('Connect.TButton', font=('Arial', 10, 'bold'))
        style.configure('Action.TButton', font=('Arial', 9))
        
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights for responsive design
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        
        # Connection Section
        conn_frame = ttk.LabelFrame(main_frame, text="Connection Settings", padding="15")
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
        sub_frame = ttk.LabelFrame(main_frame, text="Subscribe to Topic", padding="15")
        sub_frame.grid(row=1, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        sub_frame.columnconfigure(0, weight=1)

        topic_sub_frame = ttk.Frame(sub_frame)
        topic_sub_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))
        topic_sub_frame.columnconfigure(0, weight=1)

        ttk.Label(topic_sub_frame, text="Topic:", style='Title.TLabel').grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.topic_sub = ttk.Entry(topic_sub_frame, font=('Arial', 10))
        self.topic_sub.grid(row=0, column=1, sticky=(tk.W, tk.E), padx=(0, 10))
        self.topic_sub.bind('<Return>', lambda e: self.subscribe())
        
        ttk.Button(topic_sub_frame, text="Subscribe", command=self.subscribe, style='Action.TButton').grid(row=0, column=2)

        # Publish Section
        pub_frame = ttk.LabelFrame(main_frame, text="Publish Message", padding="15")
        pub_frame.grid(row=2, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 15))
        pub_frame.columnconfigure(0, weight=1)

        ttk.Label(pub_frame, text="Topic:", style='Title.TLabel').grid(row=0, column=0, sticky='w', pady=(0, 5))
        self.topic_pub = ttk.Entry(pub_frame, font=('Arial', 10))
        self.topic_pub.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=(0, 10))

        ttk.Label(pub_frame, text="Message (JSON):", style='Title.TLabel').grid(row=1, column=0, sticky='nw', pady=(0, 5))
        
        # Message text area with better styling
        msg_frame = ttk.Frame(pub_frame)
        msg_frame.grid(row=1, column=1, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        msg_frame.columnconfigure(0, weight=1)
        
        self.message = scrolledtext.ScrolledText(msg_frame, width=50, height=6, font=('Consolas', 10), 
                                               wrap=tk.WORD, relief='solid', borderwidth=1)
        self.message.grid(row=0, column=0, sticky=(tk.W, tk.E))
        
        # Add sample JSON
        sample_json = '{\n  "message": "Hello MQTT",\n  "timestamp": "2024-01-01T00:00:00Z"\n}'
        self.message.insert('1.0', sample_json)

        publish_frame = ttk.Frame(pub_frame)
        publish_frame.grid(row=2, column=1, sticky='w')
        ttk.Button(publish_frame, text="Publish", command=self.publish, style='Action.TButton').pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(publish_frame, text="Clear", command=self.clear_message, style='Action.TButton').pack(side=tk.LEFT)

        # Log Section
        log_frame = ttk.LabelFrame(main_frame, text="Activity Log", padding="15")
        log_frame.grid(row=3, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 0))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)

        self.log = scrolledtext.ScrolledText(log_frame, width=70, height=12, state='disabled', 
                                           font=('Consolas', 9), wrap=tk.WORD, relief='solid', borderwidth=1)
        self.log.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure text tags for different message alignments and colors
        self.log.tag_configure("sent", justify='right', foreground='#0066cc', background='#e6f3ff')
        self.log.tag_configure("received", justify='left', foreground='#009900', background='#f0fff0')
        self.log.tag_configure("info", justify='center', foreground='#666666')
        self.log.tag_configure("error", justify='center', foreground='#cc0000', background='#ffe6e6')
        self.log.tag_configure("success", justify='center', foreground='#009900', background='#f0fff0')
        self.log.tag_configure("warning", justify='center', foreground='#ff6600', background='#fff3e6')
        
        # Add clear log button
        ttk.Button(log_frame, text="Clear Log", command=self.clear_log, style='Action.TButton').grid(row=1, column=0, sticky='w', pady=(10, 0))

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
            'INFO': 'info'
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
        """Callback for received messages"""
        try:
            payload = msg.payload.decode('utf-8')
            self.log_msg(f"Received from [{msg.topic}]: {payload}", "RECEIVED")
        except UnicodeDecodeError:
            self.log_msg(f"Received binary data from [{msg.topic}]", "RECEIVED")

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
                self.topic_sub.delete(0, tk.END)  # Clear input after successful subscription
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
            # Validate JSON format
            json.loads(msg)
            self.client.publish(topic, msg)
            self.log_msg(f"Published to [{topic}]: {msg}", "SENT")
        except json.JSONDecodeError:
            self.log_msg("Error: Message is not valid JSON format", "ERROR")
        except Exception as e:
            self.log_msg(f"Publish failed: {str(e)}", "ERROR")

if __name__ == "__main__":
    root = tk.Tk()
    app = MQTTApp(root)
    root.mainloop()