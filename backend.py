import os
import math
import random
from collections import defaultdict
from flask import Flask, jsonify, request
from flask_cors import CORS
# --- NEW IMPORTS ---
from flask_socketio import SocketIO, emit

# --- CONFIGURATION ---
SAVE_FILE = "adjacency_matrix.txt"

# --- DC_digraph Class (No changes) ---
#
class DC_digraph:
    def __init__(self):
        self.vertices = []
        self.adj_out = defaultdict(set)
        self.adj_in = defaultdict(set)
        self.history = []
        self.redo_stack = []

    def build_vertices(self, a, b, c, d, e, f):
        # (This function is unchanged)
        vert_UN = [f'UN{i+1}' for i in range(a)]
        vert_IN = [f'IN{i+1}' for i in range(b)]
        vert_OU = [f'OU{i+1}' for i in range(c)]
        vert_VE = [f'VE{i+1}' for i in range(d)]
        vert_VA = [f'VA{i+1}' for i in range(e)]
        vert_TR = [f'TR{i+1}' for i in range(f)]
        self.vertices = vert_UN + vert_IN + vert_OU + vert_VE + vert_VA + vert_TR

    def save_state(self):
        state = {
            'vertices': self.vertices.copy(),
            'adj_out': {k: v.copy() for k, v in self.adj_out.items()},
            'adj_in': {k: v.copy() for k, v in self.adj_in.items()}
        }
        self.history.append(state)
        self.redo_stack.clear()
        if len(self.history) > 50: self.history.pop(0)

    def undo(self):
        if not self.history: return False
        current_state = {
            'vertices': self.vertices.copy(),
            'adj_out': {k: v.copy() for k, v in self.adj_out.items()},
            'adj_in': {k: v.copy() for k, v in self.adj_in.items()}
        }
        self.redo_stack.append(current_state)
        previous_state = self.history.pop()
        self.vertices = previous_state['vertices']
        self.adj_out = {k: v.copy() for k, v in previous_state['adj_out'].items()}
        self.adj_in = {k: v.copy() for k, v in previous_state['adj_in'].items()}
        return True

    def redo(self):
        if not self.redo_stack: return False
        current_state = {
            'vertices': self.vertices.copy(),
            'adj_out': {k: v.copy() for k, v in self.adj_out.items()},
            'adj_in': {k: v.copy() for k, v in self.adj_in.items()}
        }
        self.history.append(current_state)
        redo_state = self.redo_stack.pop()
        self.vertices = redo_state['vertices']
        self.adj_out = {k: v.copy() for k, v in redo_state['adj_out'].items()}
        self.adj_in = {k: v.copy() for k, v in redo_state['adj_in'].items()}
        return True

    def add_edge(self, dc1, dc2):
        if dc1 in self.vertices and dc2 in self.vertices:
            if dc2 not in self.adj_out[dc1]:
                self.save_state()
                self.adj_out[dc1].add(dc2)
                self.adj_in[dc2].add(dc1)
                return True
        return False

    def remove_edge(self, dc1, dc2):
        if dc1 in self.vertices and dc2 in self.vertices:
            if dc2 in self.adj_out[dc1]:
                self.save_state()
                self.adj_out[dc1].remove(dc2)
                self.adj_in[dc2].remove(dc1)
                return True
        return False

    def delete_node(self, node):
        if node not in self.vertices: return False
        self.save_state()
        for target in list(self.adj_out[node]):
            self.adj_in[target].remove(node)
        for source in list(self.adj_in[node]):
            self.adj_out[source].remove(node)
        del self.adj_out[node]
        del self.adj_in[node]
        self.vertices.remove(node)
        return True

# --- File Handlers (No changes) ---
#
def save_adj_matrix_to_file(graph, filename):
    vertices = graph.vertices[:]
    n = len(vertices)
    adj_matrix = [[0] * n for _ in range(n)]
    node_to_idx = {node: i for i, node in enumerate(vertices)}
    for source in vertices:
        if source not in node_to_idx: continue
        i = node_to_idx[source]
        for target in graph.adj_out[source]:
            if target not in node_to_idx: continue
            j = node_to_idx[target]
            adj_matrix[i][j] = 1
    try:
        with open(filename, 'w') as f:
            f.write("Adjacency Matrix:\n")
            header = "     " + " ".join(f"{v:<5}" for v in vertices)
            f.write(header + "\n")
            for v, row in zip(vertices, adj_matrix):
                row_str = " ".join(f"{val:<5}" for val in row)
                f.write(f"{v:<5} " + row_str + "\n")
        return True
    except IOError as e:
        print(f"Error saving adjacency matrix to {filename}: {e}")
        return False

#
def load_adj_matrix_from_file(graph, filename):
    if not os.path.exists(filename): return False
    try:
        with open(filename, 'r') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]
            if not lines or not lines[0].startswith("Adjacency Matrix:"): return False
            header_line = lines[1]
            matrix_lines = lines[2:]
            vertex_names = header_line.split()
            graph.vertices = vertex_names
            n = len(vertex_names)
            adj_matrix = []
            for line in matrix_lines:
                parts = line.split()
                row_label = parts[0]
                if row_label not in vertex_names: continue
                row_data = [int(x) for x in parts[1:]]
                while len(row_data) < n:
                    if not matrix_lines: break
                    next_line = matrix_lines.pop(0).split()
                    if next_line and next_line[0] in vertex_names:
                        matrix_lines.insert(0, ' '.join(next_line))
                        break
                    row_data.extend([int(x) for x in next_line])
                if len(row_data) == n:
                    adj_matrix.append((row_label, row_data))
            adj_matrix_sorted = sorted(adj_matrix, key=lambda x: vertex_names.index(x[0]))
            graph.adj_out = defaultdict(set)
            graph.adj_in = defaultdict(set)
            for i, (row_label, row) in enumerate(adj_matrix_sorted):
                source = row_label
                for j, val in enumerate(row):
                    if val:
                        target = graph.vertices[j]
                        graph.adj_out[source].add(target)
                        graph.adj_in[target].add(source)
        return True
    except Exception as e:
        print(f"Error loading adjacency matrix from {filename}: {e}")
        return False

# --- Layout Logic ---
#
def get_v_model_layout(graph):
    control_types = ["UN", "IN", "OU", "VE", "VA", "TR"]
    grouped = {typ: [] for typ in control_types}
    for v in graph.vertices:
        for typ in control_types:
            if v.startswith(typ):
                grouped[typ].append(v); break
    active_types = [typ for typ in control_types if grouped[typ]]
    
    # --- MODIFIED: Flip the V-Model by inverting the Y-coordinates ---
    cluster_centers = {
        # Original UN/VA y=400, OU y=-400. New: UN/VA y=-400, OU y=400
        'UN': (-500, -400), # Top Left -> Bottom Left
        'IN': (-250, 0),    # Center Left (unchanged)
        'OU': (0, 400),     # Bottom Center -> Top Center
        'VE': (250, 0),     # Center Right (unchanged)
        'VA': (500, -400),  # Top Right -> Bottom Right
        'TR': (600, 0)      # Right (unchanged)
    }
    # --- END MODIFIED ---
    
    new_pos = {}
    for typ in active_types:
        if typ not in cluster_centers: continue
        nodes_in_type = sorted(grouped[typ], key=lambda s: int(s[len(typ):]) if s[len(typ):].isdigit() else 0)
        N = len(nodes_in_type)
        if N == 0: continue
        (Cx, Cy) = cluster_centers[typ]
        golden_angle = math.pi * (3. - math.sqrt(5.))
        max_radius = 27 + 18 * math.sqrt(N) 
        for j, v in enumerate(nodes_in_type):
            if N == 1:
                new_pos[v] = {"x": Cx, "y": Cy}; continue
            theta = j * golden_angle
            r = max_radius * math.sqrt(j / max(1, N-1))
            x = Cx + r * math.cos(theta)
            y = Cy + r * math.sin(theta)
            new_pos[v] = {"x": x, "y": y}
    return new_pos

#
def get_type_layout(graph):
    control_types = ["UN", "IN", "OU", "VE", "VA", "TR"]
    grouped = {typ: [] for typ in control_types}
    for v in graph.vertices:
        for typ in control_types:
            if v.startswith(typ):
                grouped[typ].append(v); break
    active_types = [typ for typ in control_types if grouped[typ]]
    if not active_types: return {}
    
    # --- MODIFIED VALUES ---
    COLUMN_WIDTH = 600  # Increased by 100% (from 300)
    ROW_HEIGHT = 16     # Decreased by 80% (from 80)
    # --- END MODIFICATION ---

    new_pos = {}
    for i, typ in enumerate(active_types):
        x = i * COLUMN_WIDTH
        nodes_in_type = sorted(grouped[typ], key=lambda s: int(s[len(typ):]) if s[len(typ):].isdigit() else 0)
        for j, v in enumerate(nodes_in_type):
            y = j * ROW_HEIGHT
            new_pos[v] = {"x": x, "y": y}
    return new_pos

# --- Helper Function (No changes) ---
def convert_to_cytoscape(graph):
    elements = []
    color_map = {
        'UN': '#AED581', 'IN': '#81D4FA', 'OU': '#FFF176',
        'VE': '#FFB74D', 'VA': '#F48FB1', 'TR': '#E0E0E0'
    }
    for node in graph.vertices:
        node_type = node[:2]
        color = color_map.get(node_type, '#BDBDBD')
        elements.append({
            "data": { "id": node, "label": node, "type": node_type, "color": color }
        })
    for source, targets in graph.adj_out.items():
        for target in targets:
            elements.append({
                "data": { "id": f"{source}->{target}", "source": source, "target": target }
            })
    return elements

# --- Flask & Socket.IO Setup ---
app = Flask(__name__)
CORS(app)
# --- NEW: Wrap app with SocketIO ---
socketio = SocketIO(app, cors_allowed_origins="*")

# --- Load graph into memory on startup ---
print(f"Attempting to load graph from {SAVE_FILE}...")
g = DC_digraph()
if not load_adj_matrix_from_file(g, SAVE_FILE):
    print("No save file found or failed to load. Using empty graph.")
print(f"Graph loaded with {len(g.vertices)} vertices.")


# --- NEW: SOCKET.IO EVENT HANDLERS ---
# These replace the old @app.route endpoints

@socketio.on('connect')
def handle_connect():
    """Called when a new user connects."""
    print(f"Client connected: {request.sid}")
    # Send the current graph state *only to the new user*
    emit('graph_loaded', convert_to_cytoscape(g))

@socketio.on('disconnect')
def handle_disconnect():
    """Called when a user disconnects."""
    print(f"Client disconnected: {request.sid}")

@socketio.on('load_layout_vmodel')
def handle_vmodel_layout():
    """Sends V-Model layout positions to the requesting client."""
    # Layouts are just data, no need to broadcast
    emit('layout_applied', get_v_model_layout(g))

@socketio.on('load_layout_type')
def handle_type_layout():
    """Sends Sort-by-Type layout positions to the-requesting client."""
    emit('layout_applied', get_type_layout(g))

@socketio.on('add_node')
def handle_add_node(data):
    """Adds a node and broadcasts the change to ALL clients."""
    prefix = data.get('type', 'UN').strip().upper()
    control_types = ["UN", "IN", "OU", "VE", "VA", "TR"]
    if prefix not in control_types:
        return # Or emit an error

    #
    nums = [int(v[len(prefix):]) for v in g.vertices if v.startswith(prefix) and v[len(prefix):].isdigit()]
    next_num = 1
    if nums:
        nums_set = set(nums)
        for i in range(1, max(nums) + 2):
            if i not in nums_set:
                next_num = i; break
    
    new_vertex = f"{prefix}{next_num}"
    
    g.save_state()
    g.vertices.append(new_vertex)
    save_adj_matrix_to_file(g, SAVE_FILE)
    
    color_map = {'UN': '#AED581', 'IN': '#81D4FA', 'OU': '#FFF176', 'VE': '#FFB74D', 'VA': '#F48FB1', 'TR': '#E0E0E0'}
    new_node_data = {
        "data": { "id": new_vertex, "label": new_vertex, "type": prefix, "color": color_map.get(prefix, '#BDBDBD') }
    }
    
    # --- NEW: Broadcast this event to ALL connected clients ---
    socketio.emit('node_added', new_node_data)

@socketio.on('add_edge')
def handle_add_edge(data):
    """Adds an edge and broadcasts the change to ALL clients."""
    source = data.get('source')
    target = data.get('target')
    
    if g.add_edge(source, target):
        save_adj_matrix_to_file(g, SAVE_FILE)
        new_edge_data = {
            "data": {"id": f"{source}->{target}", "source": source, "target": target}
        }
        # --- NEW: Broadcast this event to ALL connected clients ---
        socketio.emit('edge_added', new_edge_data)

@socketio.on('remove_edge')
def handle_remove_edge(data):
    """Removes an edge and broadcasts the change to ALL clients."""
    source = data.get('source')
    target = data.get('target')
    
    if g.remove_edge(source, target):
        save_adj_matrix_to_file(g, SAVE_FILE)
        # --- NEW: Broadcast this event to ALL connected clients ---
        socketio.emit('edge_removed', {"id": f"{source}->{target}"})

@socketio.on('remove_node')
def handle_remove_node(data):
    """Removes a node and broadcasts the change to ALL clients."""
    node_id = data.get('id')
    
    if g.delete_node(node_id):
        save_adj_matrix_to_file(g, SAVE_FILE)
        # --- NEW: Broadcast this event to ALL connected clients ---
        socketio.emit('node_removed', {"id": node_id})

@socketio.on('undo')
def handle_undo():
    """Performs undo and broadcasts the ENTIRE new graph to ALL clients."""
    if g.undo():
        save_adj_matrix_to_file(g, SAVE_FILE)
        # Undo/Redo requires a full graph resync
        socketio.emit('graph_loaded', convert_to_cytoscape(g))

@socketio.on('redo')
def handle_redo():
    """Performs redo and broadcasts the ENTIRE new graph to ALL clients."""
    if g.redo():
        save_adj_matrix_to_file(g, SAVE_FILE)
        # Undo/Redo requires a full graph resync
        socketio.emit('graph_loaded', convert_to_cytoscape(g))


# --- NEW: Run the Server with Socket.IO ---
if __name__ == "__main__":
    print(f"Backend server running. Access by opening index.html or visiting http://<your-ip>:5000")
    # --- Use 0.0.0.0 to be accessible on the network ---
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)