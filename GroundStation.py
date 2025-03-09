from optparse import Values
import sys
import serial
import serial.tools.list_ports
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QGridLayout, QWidget, QPushButton, QTextEdit, QLineEdit, QComboBox
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QKeySequence, QAction
import pyqtgraph as pg

class GroundStation(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ground Station")
        self.setGeometry(100, 100, 1200, 800)

        # Graph setup for multiple telemetry parameters
        self.temp_plot = pg.PlotWidget(title="Temperature (ºC)")
        self.altitude_plot = pg.PlotWidget(title="Altitude (m)")
        self.pressure_plot = pg.PlotWidget(title="Pressure (Pa)")
        self.gyro_plot = pg.PlotWidget(title="Gyroscope [X, Y, Z]")
        self.accel_plot = pg.PlotWidget(title="Accelerometer [X, Y, Z] (m/s²)")
        self.velocity_plot = pg.PlotWidget(title="Velocity (m/s)")

        self.time_data = []  # Time axis for graphs
        self.temp_data, self.altitude_data, self.pressure_data = [], [], []
        self.gyro_x_data, self.gyro_y_data, self.gyro_z_data = [], [], []
        self.accel_x_data, self.accel_y_data, self.accel_z_data = [], [], []
        self.velocity_data = []

        self.temp_curve = self.temp_plot.plot(pen='b')
        self.altitude_curve = self.altitude_plot.plot(pen='y')
        self.pressure_curve = self.pressure_plot.plot(pen='r')
        self.gyro_x_curve = self.gyro_plot.plot(pen='g')
        self.gyro_y_curve = self.gyro_plot.plot(pen='m')
        self.gyro_z_curve = self.gyro_plot.plot(pen='c')
        self.accel_x_curve = self.accel_plot.plot(pen='g')
        self.accel_y_curve = self.accel_plot.plot(pen='m')
        self.accel_z_curve = self.accel_plot.plot(pen='c')
        self.velocity_curve = self.velocity_plot.plot(pen='b')

        # Serial terminal setup
        self.text_area = QTextEdit(self)
        self.text_area.setReadOnly(True)
        self.command_log = QTextEdit(self)
        self.command_log.setReadOnly(True)
        self.command_log.setMaximumHeight(50)

        self.command_input = QLineEdit(self)  # This is the text box
        self.command_input.setPlaceholderText("Type a command...")  # Optional
        send_button = QPushButton("Send")
        send_button.setStyleSheet("""
            QPushButton {
                border-radius: 10px;
                padding: 5px;
                background-color: #0078D7;  /* Windows-style blue */
                color: white;
                border: 1px solid #005A9E;
            }
            QPushButton:pressed {
                background-color: #005A9E;
            }
        """)
        send_button.clicked.connect(self.send_custom_command)
        self.command_input.returnPressed.connect(self.send_custom_command)

        command_input_layout = QHBoxLayout()

        # Set fixed height to prevent vertical expansion
        self.command_input.setFixedHeight(25)
        send_button.setFixedHeight(25)

        # Add widgets to the horizontal layout
        command_input_layout.addWidget(self.command_input)
        command_input_layout.addWidget(send_button)

        # info display
        self.data_info = QTextEdit(self)
        self.data_info.setReadOnly(True)
        self.data_info.setMaximumHeight(125)  # Adjust height as needed
        self.data_info.setStyleSheet("background-color: #222; color: #fff;")  # Dark theme

        # Dropdown to select serial port
        self.port_selector = QComboBox()
        self.populate_serial_ports()
        self.refresh_ports_button = QPushButton("Refresh Ports")
        self.refresh_ports_button.clicked.connect(self.populate_serial_ports)

        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.connect_serial)

        self.launch_button = QPushButton("Launch")
        self.launch_button.setStyleSheet("""
            QPushButton {
                background-color: #4E8F6C;  /* Soft pastel green */
                color: white;
                font-size: 16px;
                border-radius: 10px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #A3D977;  /* Slightly brighter pastel green on hover */
            }
        """)
        self.launch_button.clicked.connect(lambda: self.send_command("LAUNCH"))

        self.abort_button = QPushButton("Stop/Abort")
        self.abort_button.setStyleSheet("""
            QPushButton {
                background-color: #C75C5C;  /* Soft pastel red */
                color: white;
                font-size: 16px;
                border-radius: 10px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #FF9A9E;  /* Slightly lighter on hover */
            }
        """)
        self.abort_button.clicked.connect(lambda: self.send_command("ABORT"))

        self.reset_button = QPushButton("Reset Time")
        self.reset_button.clicked.connect(self.reset_graphs)  

        # Layout
        graph_layout = QGridLayout()
        graph_layout.addWidget(self.temp_plot, 0, 0)
        graph_layout.addWidget(self.altitude_plot, 0, 1)
        graph_layout.addWidget(self.pressure_plot, 0, 2)
        graph_layout.addWidget(self.gyro_plot, 1, 0)
        graph_layout.addWidget(self.accel_plot, 1, 1)
        graph_layout.addWidget(self.velocity_plot, 1, 2)

        controls_layout = QVBoxLayout()
        controls_layout.addWidget(self.text_area)
        controls_layout.addWidget(self.data_info)  # Inserted field
        controls_layout.addWidget(self.command_log)
        controls_layout.addLayout(command_input_layout)  # Input + button in one row
        controls_layout.addWidget(self.port_selector)
        controls_layout.addWidget(self.refresh_ports_button)
        controls_layout.addWidget(self.connect_button)
        controls_layout.addWidget(self.launch_button)
        controls_layout.addWidget(self.abort_button)
        controls_layout.addWidget(self.reset_button)

        main_layout = QHBoxLayout()
        main_layout.addLayout(graph_layout, stretch=3)
        main_layout.addLayout(controls_layout, stretch=1)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        # Serial connection variables
        self.serial_conn = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.read_serial_data)
        self.timer.start(100)

        self.reconnect_timer = QTimer()
        self.reconnect_timer.timeout.connect(self.check_serial_connection)
        self.reconnect_timer.start(5000)

        self.time_offset = None
        

        # Create menu bar
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("File")

        # Create Close action
        exit_action = QAction("Close", self)
        exit_action.setShortcut(QKeySequence("Ctrl+W"))  # Try "Ctrl+W" first
        exit_action.setShortcutContext(Qt.ShortcutContext.WindowShortcut)  
        exit_action.triggered.connect(self.close)

        file_menu.addAction(exit_action)
        self.addAction(exit_action)

    def populate_serial_ports(self):
        ports = serial.tools.list_ports.comports()
        self.port_selector.clear()
        for port in ports:
            self.port_selector.addItem(port.device)

    def connect_serial(self):
        port_name = self.port_selector.currentText()
        if port_name:
            self.serial_conn = serial.Serial(port_name, 115200, timeout=1)
            self.text_area.append(f"Connected to {port_name}")
            self.timer.start(100)
        else:
            self.text_area.append("No port selected!")

    def check_serial_connection(self):
        if self.serial_conn and not self.serial_conn.is_open:
            self.text_area.append("Connection lost. Attempting to reconnect...")
            self.connect_serial()

    def reset_graphs(self):
        """Reset all graph data and time offset"""
        self.time_data.clear()
        self.time_offset = None  # Reset time offset
        self.temp_data.clear()
        self.altitude_data.clear()
        self.pressure_data.clear()
        self.gyro_x_data.clear()
        self.gyro_y_data.clear()
        self.gyro_z_data.clear()
        self.accel_x_data.clear()
        self.accel_y_data.clear()
        self.accel_z_data.clear()
        self.velocity_data.clear()

        self.temp_curve.setData([], [])
        self.altitude_curve.setData([], [])
        self.pressure_curve.setData([], [])
        self.gyro_x_curve.setData([], [])
        self.gyro_y_curve.setData([], [])
        self.gyro_z_curve.setData([], [])
        self.accel_x_curve.setData([], [])
        self.accel_y_curve.setData([], [])
        self.accel_z_curve.setData([], [])
        self.velocity_curve.setData([],[])


    def read_serial_data(self):
    #Read serial data from the ESP32 and update the UI
        if self.serial_conn and self.serial_conn.in_waiting:
            data = self.serial_conn.readline().decode('utf-8').strip()
            self.text_area.append(data)  # Display data in UI
            
            try:
                data = self.serial_conn.readline().decode('utf-8').strip()
                self.text_area.append(data)
            
            # Parse CSV formatted telemetry data
                parts = data.split(",")
                if len(parts) >= 10:  # Ensure sufficient data is received
                    try:
                        time_value = float(parts[0])   # First value is time
                        altitude = float(parts[1])     # Second is altitude
                        temperature = float(parts[2])  # Third is temperature
                        pressure = float(parts[3])     # Fourth is pressure
                        accel_x = float(parts[4])
                        accel_y = float(parts[5])
                        accel_z = float(parts[6])
                        gyro_x = float(parts[7])
                        gyro_y = float(parts[8])
                        gyro_z = float(parts[9])
                        velocity = float(parts[13])
                        gps_lat = float(parts[10])
                        gps_long = float(parts[11])
                        gps_alt = float(parts[12])
                        gps_fix = int(parts[14])

                        self.update_data_info(gps_lat, gps_long, gps_alt, accel_x, accel_y, accel_z, gps_fix)

                        if self.time_offset is None:
                            self.time_offset = time_value  # Set initial offset

                        adjusted_time = time_value - self.time_offset  # Offset the time

                        # Store adjusted time values
                        self.time_data.append(adjusted_time)
                        self.altitude_data.append(float(parts[1]))  # Assuming second column is temperature
                        self.temp_data.append(float(parts[2]))  # Assuming third column is altitude
                        self.pressure_data.append(float(parts[3]))  # Assuming fourth column is pressure
                        self.accel_x_data.append(float(parts[4]))
                        self.accel_y_data.append(float(parts[5]))
                        self.accel_z_data.append(float(parts[6]))
                        self.gyro_x_data.append(float(parts[7]))
                        self.gyro_y_data.append(float(parts[8]))
                        self.gyro_z_data.append(float(parts[9]))
                        self.velocity_data.append(float(parts[13]))

                        # Update plots with both X (time) and Y (data)
                        self.temp_curve.setData(self.time_data, self.temp_data)
                        self.altitude_curve.setData(self.time_data, self.altitude_data)
                        self.pressure_curve.setData(self.time_data, self.pressure_data)
                        self.gyro_x_curve.setData(self.time_data, self.gyro_x_data)
                        self.gyro_y_curve.setData(self.time_data, self.gyro_y_data)
                        self.gyro_z_curve.setData(self.time_data, self.gyro_z_data)
                        self.accel_x_curve.setData(self.time_data, self.accel_x_data)
                        self.accel_y_curve.setData(self.time_data, self.accel_y_data)
                        self.accel_z_curve.setData(self.time_data, self.accel_z_data)
                        self.velocity_curve.setData(self.time_data, self.velocity_data)

                        # Update graphs with (x, y) values where x = time
                        self.altitude_curve.setData([x[0] for x in self.altitude_data], [x[1] for x in self.altitude_data])
                        self.temp_curve.setData([x[0] for x in self.temp_data], [x[1] for x in self.temp_data])
                        self.pressure_curve.setData([x[0] for x in self.pressure_data], [x[1] for x in self.pressure_data])
                        self.gyro_x_curve.setData([x[0] for x in self.gyro_x_data], [x[1] for x in self.gyro_x_data])
                        self.gyro_y_curve.setData([x[0] for x in self.gyro_y_data], [x[1] for x in self.gyro_y_data])
                        self.gyro_z_curve.setData([x[0] for x in self.gyro_z_data], [x[1] for x in self.gyro_z_data])
                        self.accel_x_curve.setData([x[0] for x in self.accel_x_data], [x[1] for x in self.accel_x_data])
                        self.accel_y_curve.setData([x[0] for x in self.accel_y_data], [x[1] for x in self.accel_y_data])
                        self.accel_z_curve.setData([x[0] for x in self.accel_z_data], [x[1] for x in self.accel_z_data])
                        self.velocity_curve.setData([x[0] for x in self.velocity_data], [x[1] for x in self.velocity_data])

                        if self.time_offset is None:
                            self.time_offset = time_value  # Store first timestamp

                        adjusted_time = time_value - self.time_offset  # Offset current time

                        # Update UI with adjusted time
                        self.text_area.append(f"Time: {adjusted_time} ms, Data: {Values[1:]}")
                        

                    except ValueError:
                        self.text_area.append("Error parsing telemetry data")

            except Exception as e:
                self.text_area.append(f"Error: {str(e)}")
        
    def reset_time_offset(self):
        """Reset time offset to the current timestamp"""
        self.time_offset = None  # Will be updated with next received timestamp
    def update_serial_ports(self):
        """Scans and updates available serial ports in the dropdown."""
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_selector.clear()
        self.port_selector.addItems(ports)
        print(f"Available Ports: {ports}")

    def connect_to_selected_port(self):
        """Connects to the selected serial port."""
        selected_port = self.port_selector.currentText()
        if selected_port:
            try:
                self.serial = serial.Serial(selected_port, self.baud_rate)
                print(f"Connected to {selected_port}")
            except serial.SerialException as e:
                print(f"Failed to connect: {e}")
        else:
            print("No port selected!")
    def send_command(self, command):
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.write(f"{command}\n".encode())
            self.command_log.append(f"Sent: {command}")
        else:
            self.command_log.append("Error: Serial not connected!")

    def update_data_info(self, gps_lat, gps_long, gps_alt, accel_x, accel_y, accel_z, gps_fix):
        info_text = (
            f"GPS Lat: {gps_lat}\n"
            f"GPS Long: {gps_long}\n"
            f"GPS Alt: {gps_alt}m\n"
            f"GPS Fix: {gps_fix}\n"
            f"Accel X: {accel_x} m/s²\n"
            f"Accel Y: {accel_y} m/s²\n"
            f"Accel Z: {accel_z} m/s²"
        )
        self.data_info.setPlainText(info_text)
    def send_custom_command(self):
        command = self.command_input.text().strip()
        if command:
            self.command_log.append(f"Sent: {command}")
            self.command_input.clear()  # Clear the input after sending
            # Here you should send the command through serial if needed

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GroundStation()
    window.show()
    sys.exit(app.exec())