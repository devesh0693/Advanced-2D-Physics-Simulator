# Advanced 2D Physics Simulator



A feature-rich 2D physics simulation environment built with Python, leveraging pygame for rendering and pymunk for accurate physics calculations. This simulator provides an interactive playground for experimenting with physics objects in a customizable environment.

## Features

- **Interactive Physics Environment**: Create and manipulate various physics objects in real-time
- **Multiple Object Types**: Players, boxes, bouncers, coins, and more
- **Camera Controls**: Pan and zoom functionality for exploring the simulation space
- **Object Manipulation**: Drag and drop objects with mouse
- **Complete Force Controls**: Apply forces to objects and modify global gravity
- **Score System**: Collect coins to increase your score
- **Event Logging**: Comprehensive logging of simulation events
- **Debugging Tools**: Toggle pymunk debug rendering to visualize physics bodies
- **Modern UI**: Clean interface using CustomTkinter with intuitive controls

## Requirements

- Python 3.7+
- Dependencies:
  - customtkinter
  - pygame
  - pymunk
  - pillow (PIL)
  - numpy

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/physics-simulator.git
   cd physics-simulator
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install customtkinter pygame pymunk pillow numpy
   ```

4. Create an assets directory and add the required images:
   ```bash
   mkdir assets
   ```
   
   Add the following images to the assets folder:
   - ball.png
   - box.png
   - bouncer.png
   - coin.png

## Usage

Run the simulator:
```bash
python Simulator.py
```

### Controls

- **Mouse**: 
  - Left-click and drag to move objects
  - Right-click to spawn a ball
- **WASD**: Move the player object
- **Arrow Keys**: Pan the camera
- **Mouse Wheel**: Zoom in/out
- **GUI Buttons**:
  - Add different objects
  - Reset simulation
  - Toggle debug view

## Architecture

The simulator is built on a hybrid architecture:
- **CustomTkinter**: Provides the application window and UI controls
- **Pygame**: Handles rendering of the physics simulation
- **Pymunk**: Powers the physics calculations and collision detection

Key components:
- `SimulationApp`: Main application class
- `Camera`: Handles view transformations
- `Entity`: Base class for all physics objects
- Various entity types: `ControllableEntity`, `BoxEntity`, `BouncerEntity`, `CoinEntity`

## Extending and Customizing

### Adding New Entity Types

1. Create a new class that inherits from `Entity`:
   ```python
   class NewEntity(Entity):
       def __init__(self, pos, space, image_path="new_entity.png", scale=0.1):
           super().__init__(pos, space, image_path, mass=15, radius=20, scale=scale,
                           collision_type=COLLISION_TYPE_NEW_ENTITY)
           # Custom properties and behaviors
           self.special_property = 100
           
       def special_method(self):
           # Custom behavior
           pass
   ```

2. Add a new collision type at the top of the file:
   ```python
   COLLISION_TYPE_NEW_ENTITY = 10  # Choose an unused number
   ```

3. Add the entity creation function to `SimulationApp`:
   ```python
   def add_new_entity(self, pos):
       obj = NewEntity(pos, self.space)
       self.all_sprites.add(obj)
       self.entities.append(obj)
   ```

4. Add a button to the UI:
   ```python
   self.add_new_entity_button = ctk.CTkButton(
       self.left_controls_frame, 
       text="Add New Entity", 
       command=lambda: self.add_object_at_mouse_center("new_entity")
   )
   self.add_new_entity_button.pack(pady=3, fill="x")
   ```

5. Update `_add_object_at_pos` method to handle your new entity:
   ```python
   elif entity_type_str == "new_entity":
       obj = NewEntity(world_pos, self.space)
   ```

## Forking and Contributing

### How to Fork

1. Fork the repository on GitHub
2. Clone your fork:
   ```bash
   git clone https://github.com/your-username/physics-simulator.git
   ```
3. Add the original repo as upstream:
   ```bash
   git remote add upstream https://github.com/original-username/physics-simulator.git
   ```

### Making Changes

1. Create a new branch for your feature:
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. Make your changes and commit:
   ```bash
   git add .
   git commit -m "Add my new feature"
   ```

3. Push to your fork:
   ```bash
   git push origin feature/my-new-feature
   ```

4. Create a Pull Request from your forked repository

### Keeping Your Fork Updated

Sync your fork with the original repository:
```bash
git fetch upstream
git checkout main
git merge upstream/main
git push origin main
```

## Scaling the Application

### Code Architecture Improvements

1. **Module Organization**: Split the codebase into separate modules:
   - `entities/`: Contains entity classes
   - `ui/`: UI-related components
   - `physics/`: Physics engine integration
   - `utils/`: Helper functions and utilities

2. **Configuration System**: Move hardcoded values to a configuration system:
   ```python
   # config.py
   CONFIG = {
       "display": {
           "width": 1000,
           "height": 600,
       },
       "physics": {
           "gravity_x": 0,
           "gravity_y": 900,
           "time_step": 1/60,
       },
       # Other configuration sections
   }
   ```

3. **Plugin System**: Create a simple plugin architecture:
   ```python
   # plugins/base.py
   class SimulatorPlugin:
       def __init__(self, app):
           self.app = app
           
       def on_init(self):
           pass
           
       def on_update(self):
           pass
           
       def on_render(self, surface):
           pass
   ```

### Performance Optimizations

1. **Spatial Partitioning**: Implement a grid or quadtree for efficient collision detection with many objects:
   ```python
   class QuadTree:
       # Implementation for spatial partitioning
       pass
   ```

2. **Object Pooling**: Reuse object instances instead of creating/destroying:
   ```python
   class EntityPool:
       def __init__(self, factory_func, initial_size=10):
           self.available = [factory_func() for _ in range(initial_size)]
           self.in_use = []
           self.factory_func = factory_func
           
       def get(self):
           if not self.available:
               self.available.append(self.factory_func())
           entity = self.available.pop()
           self.in_use.append(entity)
           return entity
           
       def release(self, entity):
           if entity in self.in_use:
               self.in_use.remove(entity)
               self.available.append(entity)
   ```

3. **Level of Detail**: Render distant objects with simplified physics:
   ```python
   def update(self):
       distance = ((self.body.position - camera.position).length)
       if distance > DETAILED_PHYSICS_THRESHOLD:
           # Use simplified physics update
           pass
       else:
           # Use detailed physics
           pass
   ```

### Networking and Multiplayer

1. **Client-Server Architecture**: Implement basic networking:
   ```python
   # server.py
   class PhysicsServer:
       def __init__(self, port=5555):
           self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
           self.server_socket.bind(("0.0.0.0", port))
           self.server_socket.listen(5)
           self.clients = []
           self.space = pymunk.Space()  # Central physics authority
           
       def start(self):
           # Handle client connections and synchronize physics
           pass
   ```

2. **State Synchronization**: Efficiently sync physics states:
   ```python
   def serialize_world_state(self):
       # Compress and encode the world state for network transmission
       state = {
           "entities": [
               {
                   "id": entity.id,
                   "pos": (entity.body.position.x, entity.body.position.y),
                   "vel": (entity.body.velocity.x, entity.body.velocity.y),
                   "angle": entity.body.angle
               }
               for entity in self.entities
           ]
       }
       return json.dumps(state)
   ```

### Data Persistence

1. **Save/Load System**: Add the ability to save and load simulations:
   ```python
   def save_simulation(self, filename):
       """Save the current simulation state to a file"""
       state = {
           "entities": [],
           "score": self.score,
           "gravity": self.space.gravity
       }
       
       for entity in self.entities:
           entity_data = {
               "type": entity.__class__.__name__,
               "position": (entity.body.position.x, entity.body.position.y),
               "velocity": (entity.body.velocity.x, entity.body.velocity.y),
               "angle": entity.body.angle
           }
           state["entities"].append(entity_data)
           
       with open(filename, 'w') as f:
           json.dump(state, f)
           
   def load_simulation(self, filename):
       """Load a simulation state from a file"""
       with open(filename, 'r') as f:
           state = json.load(f)
           
       self.reset_simulation()
       self.score = state["score"]
       self.space.gravity = tuple(state["gravity"])
       
       for entity_data in state["entities"]:
           entity_type = entity_data["type"]
           pos = tuple(entity_data["position"])
           
           if entity_type == "ControllableEntity":
               self.add_player(pos)
           elif entity_type == "BoxEntity":
               self.add_object_at_pos(pos, "box")
           # Handle other entity types
   ```

## License

[MIT License](LICENSE)

## Acknowledgments

- [Pygame](https://www.pygame.org/) - Game development library
- [Pymunk](http://www.pymunk.org/) - 2D physics library
- [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) - Modern UI toolkit
