import os
import threading
import time
import logging
import json
import tkinter as tk
from tkinter import filedialog
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from Main import variablesModel
from measurement import measurementVM

app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')

# Global variables to hold measurement state
variableSet = variablesModel()

def data_emit_callback(data_point):
    socketio.emit('new_data_point', data_point)

measureVM = measurementVM(variableSet, data_callback=data_emit_callback)
measurement_thread = None
measurement_queue = []
is_running_queue = False
STATE_FILE = "queue_state.json"

def save_queue_state():
    try:
        with open(STATE_FILE, 'w') as f:
            json.dump(measurement_queue, f)
    except Exception as e:
        logging.error(f"Failed to save queue state: {e}")

def load_queue_state():
    global measurement_queue
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                measurement_queue = json.load(f)
                # Reset statuses if they were stuck in 'running'
                for task in measurement_queue:
                    if task['status'] == 'running':
                        task['status'] = 'waiting'
        except Exception as e:
            logging.error(f"Failed to load queue state: {e}")

class SocketIOHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        socketio.emit('log_update', {'log': log_entry})

# Add SocketIO logger
log_handler = SocketIOHandler()
log_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logging.getLogger().addHandler(log_handler)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/select_file', methods=['GET'])
def select_file():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    file_paths = filedialog.askopenfilenames()
    root.destroy()
    return jsonify({"paths": list(file_paths)})

@app.route('/select_directory', methods=['GET'])
def select_directory():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    dir_path = filedialog.askdirectory()
    root.destroy()
    return jsonify({"path": dir_path})

@app.route('/add_to_queue', methods=['POST'])
def add_to_queue():
    data = request.json
    if not data or not data.get('sequenceDirectory'):
        return jsonify({"status": "error", "message": "Sequence directory is required"})
    
    sequence_input = data.get('sequenceDirectory')
    
    # Handle both single path and list of paths
    if isinstance(sequence_input, str):
        paths = [sequence_input]
    else:
        paths = sequence_input

    tasks_added = 0
    for path in paths:
        # If it's a directory, add all .dat files inside
        if os.path.isdir(path):
            import glob
            dat_files = glob.glob(os.path.join(path, "*.dat"))
            for dat_file in dat_files:
                add_single_task(dat_file, data.get('dataSaveDirectory'), data.get('dataSaveFileName'))
                tasks_added += 1
        else:
            add_single_task(path, data.get('dataSaveDirectory'), data.get('dataSaveFileName'))
            tasks_added += 1

    socketio.emit('queue_update', measurement_queue)
    save_queue_state()
    return jsonify({"status": "success", "message": f"Added {tasks_added} tasks to queue"})

def add_single_task(seq_path, save_dir, save_name_base):
    # If base name is provided, append a unique ID to avoid overwriting
    # If not, use the sequence filename as base
    if not save_name_base:
        save_name = os.path.splitext(os.path.basename(seq_path))[0]
    else:
        # Append index or timestamp to base name
        save_name = f"{save_name_base}_{len(measurement_queue) + 1}"

    task = {
        "id": int(time.time() * 1000) + len(measurement_queue),
        "sequenceDirectory": seq_path,
        "dataSaveDirectory": save_dir,
        "dataSaveFileName": save_name,
        "status": "waiting"
    }
    measurement_queue.append(task)

@app.route('/clear_queue', methods=['POST'])
def clear_queue():
    global measurement_queue
    # Only remove tasks that are 'completed' or 'error'
    measurement_queue = [t for t in measurement_queue if t['status'] in ['running', 'waiting']]
    socketio.emit('queue_update', measurement_queue)
    save_queue_state()
    return jsonify({"status": "success"})

@app.route('/delete_from_queue', methods=['POST'])
def delete_from_queue():
    global measurement_queue
    data = request.json
    task_id = data.get('id')
    if task_id:
        # Don't delete if it's currently running
        measurement_queue = [t for t in measurement_queue if not (t['id'] == task_id and t['status'] == 'running')]
        socketio.emit('queue_update', measurement_queue)
        save_queue_state()
    save_queue_state()
    return jsonify({"status": "success"})

@app.route('/reorder_queue', methods=['POST'])
def reorder_queue():
    global measurement_queue
    data = request.json
    new_order_ids = data.get('order', [])
    
    # Rebuild queue based on new order, keeping currently running tasks at their position
    new_queue = []
    # Index the current queue
    queue_map = {t['id']: t for t in measurement_queue}
    
    # First, add the provided order (only if they exist and are waiting/completed/error - though UI only allows dragging waiting)
    for tid in new_order_ids:
        if tid in queue_map:
            new_queue.append(queue_map[tid])
            
    # Ensure any tasks missing from the order (like running tasks) are kept
    for t in measurement_queue:
        if t['id'] not in new_order_ids:
            # Insert running task at its original position or start
            if t['status'] == 'running':
                new_queue.insert(0, t)
            else:
                new_queue.append(t)
            
    measurement_queue = new_queue
    socketio.emit('queue_update', measurement_queue)
    save_queue_state()
    return jsonify({"status": "success"})

@app.route('/set_property', methods=['POST'])
def set_property():
    global is_running_queue
    if is_running_queue:
        return jsonify({"status": "error", "message": "Cannot change properties while measurement is running"})
    
    data = request.json
    prop = data.get('property')
    params = data.get('params', {})
    
    def execute_manual_command():
        try:
            logging.info(f"Manual Control: Setting {prop} to {params.get('target')}")
            variableSet.currentCommand = f"Manual {prop}"
            # connect and auto-disconnect using with-statement
            with measureVM.connectionVM.connectInstrument() as instrumentsList:
                if prop == 'temp':
                    measureVM.setScanFunction.setTemp(params['target'], params['rate'], params['waittime'], instrumentsList)
                elif prop == 'field':
                    measureVM.setScanFunction.setField(params['target'], params['approach'], params['mode'], params['waittime'], instrumentsList)
                elif prop == 'pos':
                    measureVM.setScanFunction.setPos(params['target'], instrumentsList)
                elif prop == 'amp':
                    measureVM.setScanFunction.setAmp(params['target'], params['freq'], params['offset'], params['waittime'], instrumentsList)
            logging.info(f"Manual Control: {prop} set successfully.")
            variableSet.currentCommand = "Idle"
        except Exception as e:
            logging.error(f"Error in manual control: {e}")
            variableSet.currentCommand = "Manual Error"

    threading.Thread(target=execute_manual_command).start()
    return jsonify({"status": "success"})

@app.route('/start', methods=['POST'])
def start_measurement():
    global measurement_thread, is_running_queue
    if measurement_thread and measurement_thread.is_alive():
        return jsonify({"status": "error", "message": "Measurement already running"})
    
    if not measurement_queue:
        return jsonify({"status": "error", "message": "Queue is empty"})

    is_running_queue = True
    variableSet.StopMeasurementFlag = 0
    measurement_thread = threading.Thread(target=run_queue_processor)
    measurement_thread.start()
    return jsonify({"status": "success", "message": "Queue processing started"})

@app.route('/stop', methods=['POST'])
def stop_measurement():
    global is_running_queue
    is_running_queue = False
    variableSet.StopMeasurementFlag = 1
    variableSet.currentCommand = "Stopping..."
    return jsonify({"status": "success", "message": "Stop signal sent"})

@app.route('/open_folder', methods=['POST'])
def open_folder():
    data = request.json
    path = data.get('path')
    if path and os.path.exists(path):
        import subprocess
        subprocess.Popen(f'explorer "{os.path.normpath(path)}"')
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Path not found"})

@app.route('/preview_sequence', methods=['GET'])
def preview_sequence():
    path = request.args.get('path')
    if not path or not os.path.exists(path):
        return jsonify({"status": "error", "message": "Invalid path"})
    
    try:
        from sequence import sequence
        # We need a temporary sequence object to read without affecting the main one
        temp_seq = sequence(variablesModel())
        temp_seq.readSequence(path)
        return jsonify({
            "status": "success",
            "commands": temp_seq.get_sequence_list()
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

def run_queue_processor():
    global is_running_queue
    for task in measurement_queue:
        if not is_running_queue or variableSet.StopMeasurementFlag > 0:
            break
        
        if task['status'] != 'waiting':
            continue

        task['status'] = 'running'
        socketio.emit('queue_update', measurement_queue)
        save_queue_state()
        
        # Setup variables for this task
        variableSet.sequenceDirectory = task['sequenceDirectory']
        variableSet.dataSaveDirectory = task['dataSaveDirectory']
        variableSet.dataSaveFileName = task['dataSaveFileName']
        
        try:
            logging.info(f"Starting task: {task['dataSaveFileName']}")
            measureVM.sequenceVM.readSequence(variableSet.sequenceDirectory)
            
            # Send sequence steps to UI
            socketio.emit('sequence_data', {
                "fileName": task['dataSaveFileName'],
                "commands": measureVM.sequenceVM.get_sequence_list()
            })
            
            measureVM.startMeasurement()
            task['status'] = 'completed'
        except Exception as e:
            logging.error(f"Error in task {task['dataSaveFileName']}: {e}")
            task['status'] = 'error'
        
        socketio.emit('queue_update', measurement_queue)
        save_queue_state()
        
        if variableSet.StopMeasurementFlag > 0:
            break

    is_running_queue = False
    variableSet.currentCommand = "Idle"
    socketio.emit('measurement_finished', {'status': 'done'})

def status_sender():
    while True:
        socketio.sleep(1)
        status = {
            "field": variableSet.currentField,
            "fieldStatus": variableSet.fieldStatus,
            "temp": variableSet.currentTemp,
            "tempStatus": variableSet.tempStatus,
            "pos": variableSet.currentPOS,
            "posStatus": variableSet.posStatus,
            "amp": variableSet.currentAmp,
            "freq": variableSet.currentFreq,
            "heLevel": variableSet.currentHeLevel,
            "time": time.strftime("%H:%M:%S", time.localtime(variableSet.currentTime)) if variableSet.currentTime > 0 else "N/A",
            "currentCommand": variableSet.currentCommand
        }
        socketio.emit('status_update', status)

@socketio.on('connect')
def handle_connect():
    print('Client connected')

if __name__ == '__main__':
    load_queue_state()
    # Start status background task
    socketio.start_background_task(status_sender)
    
    # Open browser automatically (only once, even in debug mode)
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        import webbrowser
        threading.Timer(1, lambda: webbrowser.open("http://127.0.0.1:5000")).start()
    
    socketio.run(app, debug=True, host='127.0.0.1', port=5000)
