from PyQt5.QtGui import QIcon, QColor, QPainter, QPen, QPixmap, QPainter, QMouseEvent, QResizeEvent, QImage
from PyQt5.QtWidgets import QMainWindow, QApplication, QAbstractItemView, QRadioButton, QComboBox, \
                            QFileDialog, QWidget, QHBoxLayout, QVBoxLayout, QProgressBar, QApplication, \
                            QDialog, QLineEdit, QLabel, QPushButton, QAbstractItemView, \
                            QSizePolicy, QGroupBox, QListWidget, QFormLayout, QCheckBox
from PyQt5.QtCore import Qt, QRect, QPoint, QSettings, QTranslator, QMargins, QTimer, QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot, QEvent
#from PyQt5.QtCore import QT_TR_NOOP as tr
from PyQt5.QtOpenGL import *
from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *

from superqt import QLabeledRangeSlider, QLabeledSlider

import os, sys, re
from PIL import Image, ImageChops
import numpy as np
import mcubes
from scipy import ndimage  # For interpolation
import math

def value_to_bool(value):
    return value.lower() == 'true' if isinstance(value, str) else bool(value)

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

MODE = {}
MODE['VIEW'] = 0
MODE['ADD_BOX'] = 1
MODE['MOVE_BOX'] = 2
MODE['EDIT_BOX'] = 3
MODE['EDIT_BOX_READY'] = 4
MODE['EDIT_BOX_PROGRESS'] = 5
MODE['MOVE_BOX_PROGRESS'] = 6
MODE['MOVE_BOX_READY'] = 7
DISTANCE_THRESHOLD = 10
COMPANY_NAME = "PaleoBytes"
PROGRAM_NAME = "CT Harvester"
PROGRAM_VERSION = "0.2"
PROGRAM_AUTHOR = "Jikhan Jung"


OBJECT_MODE = 1
VIEW_MODE = 1
PAN_MODE = 2
ROTATE_MODE = 3
ZOOM_MODE = 4
MOVE_3DVIEW_MODE = 5


class WorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.

    Supported signals are:

    finished
        No data

    error
        tuple (exctype, value, traceback.format_exc() )

    result
        object data returned from processing, anything

    progress
        int indicating % progress

    '''
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)


class Worker(QRunnable):
    '''
    Worker thread

    Inherits from QRunnable to handler worker thread setup, signals and wrap-up.

    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function

    '''

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # Add the callback to our kwargs
        #self.kwargs['progress_callback'] = self.signals.progress

    @pyqtSlot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''

        # Retrieve args/kwargs here; and fire processing using them
        try:
            result = self.fn(*self.args, **self.kwargs)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done



# Define a custom OpenGL widget using QOpenGLWidget
class MCubeWidget(QGLWidget):
    def __init__(self,parent):
        super().__init__(parent=parent)
        #self.parent = parent
        self.setMinimumSize(100,100)
        #self.volume = self.read_images_from_folder( "D:/CT/CO-1/CO-1_Rec/Cropped" ) #np.zeros((10, 10, 10))  # Define the volume to visualize
        # Example usage:
        self.isovalue = 60  # Adjust the isovalue as needed
        #self.triangles, self.vertices = self.marching_cubes(self.volume,isovalue)
        #print(triangles)
        self.scale = 1.0
        self.pan_x = 0
        self.pan_y = 0
        self.temp_pan_x = 0
        self.temp_pan_y = 0
        self.rotate_x = 0
        self.rotate_y = 0
        self.temp_rotate_x = 0
        self.temp_rotate_y = 0
        self.curr_x = 0
        self.curr_y = 0
        self.down_x = 0
        self.down_y = 0
        self.temp_dolly = 0
        self.dolly = 0
        self.data_mode = OBJECT_MODE
        self.view_mode = VIEW_MODE
        self.auto_rotate = True
        self.is_dragging = False
        #self.setMinimumSize(400,400)
        self.timer = QTimer(self)
        self.timer.setInterval(50)
        self.timer.timeout.connect(self.timeout)
        self.timer.start()
        self.triangles = []
        self.gl_list_generated = False
        self.parent = parent
        self.parent.set_threed_view(self)

        self.moveButton = QLabel(self)
        self.moveButton.setPixmap(QPixmap(resource_path("move.png")).scaled(15,15))
        self.moveButton.hide()
        self.moveButton.setGeometry(0,0,15,15)
        self.moveButton.mousePressEvent = self.moveButton_mousePressEvent
        self.moveButton.mouseMoveEvent = self.moveButton_mouseMoveEvent
        self.moveButton.mouseReleaseEvent = self.moveButton_mouseReleaseEvent
        self.expandButton = QLabel(self)
        self.expandButton.setPixmap(QPixmap(resource_path("expand.png")).scaled(15,15))
        self.expandButton.hide()
        self.expandButton.setGeometry(15,0,15,15)
        self.expandButton.mousePressEvent = self.expandButton_mousePressEvent
        self.shrinkButton = QLabel(self)
        self.shrinkButton.setPixmap(QPixmap(resource_path("shrink.png")).scaled(15,15))
        self.shrinkButton.hide()
        self.shrinkButton.setGeometry(30,0,15,15)
        self.shrinkButton.mousePressEvent = self.shrinkButton_mousePressEvent
        self.cbxRotation = QCheckBox(self)
        self.cbxRotation.setText("R")
        self.cbxRotation.setChecked(True)
        self.cbxRotation.stateChanged.connect(self.cbxRotation_stateChanged)
        self.cbxRotation.setStyleSheet("QCheckBox { background-color: #323232; color: white; }")        
        self.cbxRotation.hide()
        self.cbxRotation.move(45,0)

        self.curr_slice = None
        self.curr_slice_vertices = []
        self.scale = 0.20
        self.average_coordinates = np.array([0.0,0.0,0.0], dtype=np.float64)
        self.bouding_box = None
        self.roi_box = None
        self.threadpool = QThreadPool()
        print("Multithreading with maximum %d threads" % self.threadpool.maxThreadCount())

    def progress_fn(self, n):
        #print("%d%% done" % n)
        return

    def execute_this_fn(self, progress_callback):
        progress_callback.emit(100)

        return "Done."

    def print_output(self, s):
        print(s)

    def thread_complete(self):
        #print("THREAD COMPLETE!")
        return

    def oh_no(self):
        # Pass the function to execute
        worker = Worker(self.generate_mesh) # Any other args, kwargs are passed to the run function
        worker.signals.result.connect(self.print_output)
        worker.signals.finished.connect(self.thread_complete)
        worker.signals.progress.connect(self.progress_fn)

        # Execute
        self.threadpool.start(worker)

    def expandButton_mousePressEvent(self, event):
        self.scale += 0.1
        self.resize_self()
        self.reposition_self()

    def shrinkButton_mousePressEvent(self, event):
        self.scale -= 0.1
        if self.scale < 0.1:
            self.scale = 0.1
        self.resize_self()
        self.reposition_self()

    def moveButton_mousePressEvent(self, event):
        self.down_x = event.x()
        self.down_y = event.y()
        self.view_mode = MOVE_3DVIEW_MODE

    def moveButton_mouseMoveEvent(self, event):
        self.curr_x = event.x()
        self.curr_y = event.y()
        if self.view_mode == MOVE_3DVIEW_MODE:
            self.move(self.x() + self.curr_x - self.down_x, self.y() + self.curr_y - self.down_y)
        #self.reposition_self()

    def moveButton_mouseReleaseEvent(self, event):
        self.curr_x = event.x()
        self.curr_y = event.y()
        if self.view_mode == MOVE_3DVIEW_MODE:
            self.move(self.x() + self.curr_x - self.down_x, self.y() + self.curr_y - self.down_y)

        self.view_mode = VIEW_MODE
        # get parent's geometry
        self.reposition_self()

    def reposition_self(self):
        x, y = self.x(), self.y()
        parent_geometry = self.parent.geometry()
        if y + ( self.height() / 2 ) > parent_geometry.height() / 2 :
            y = parent_geometry.height() - self.height()
        else:
            y = 0
        if x + ( self.width() / 2 ) > parent_geometry.width() / 2 :
            x = parent_geometry.width() - self.width()
        else:
            x = 0
        
        self.move(x, y)                

    def cbxRotation_stateChanged(self):
        self.auto_rotate = self.cbxRotation.isChecked()

    def resize_self(self):
        size = min(self.parent.width(),self.parent.height())
        self.resize(int(size*self.scale),int(size*self.scale))
        #print("resize:",self.parent.width(),self.parent.height())

    def generate_mesh(self):
        self.cbxRotation.show()
        self.moveButton.show()
        self.expandButton.show()
        self.shrinkButton.show()
        self.vertices, self.triangles = mcubes.marching_cubes(self.volume, self.isovalue)

        self.vertices /= 10.0

        self.average_coordinates = np.mean(self.vertices, axis=0)
        self.vertices -= self.average_coordinates

        face_normals = []
        for triangle in self.triangles:
            v0 = self.vertices[triangle[0]]
            v1 = self.vertices[triangle[1]]
            v2 = self.vertices[triangle[2]]
            edge1 = v1 - v0
            edge2 = v2 - v0
            normal = np.cross(edge1, edge2)
            norm = np.linalg.norm(normal)
            if norm == 0:
                normal = np.array([0, 0, 0])
            else:
                normal /= np.linalg.norm(normal)
            face_normals.append(normal)

        vertex_normals = np.zeros(self.vertices.shape)

        # Calculate vertex normals by averaging face normals
        for i, triangle in enumerate(self.triangles):
            for vertex_index in triangle:
                vertex_normals[vertex_index] += face_normals[i]

        # Normalize vertex normals
        '''
        norms = np.linalg.norm(vertex_normals, axis=1)
        vertex_normals = np.where(norms != 0, vertex_normals / norms[:, np.newaxis], np.array([0.0, 0.0, 0.0]))
        self.vertex_normals = vertex_normals

        '''
        for i in range(len(vertex_normals)):
            if np.linalg.norm(vertex_normals[i]) != 0:
                vertex_normals[i] /= np.linalg.norm(vertex_normals[i])
            else:
                vertex_normals[i] = np.array([0.0, 0.0, 0.0])
        
        #vertex_normals /= np.linalg.norm(vertex_normals, axis=1)[:, np.newaxis]
        self.vertex_normals = vertex_normals

        # rotate vertices
        for i in range(len(self.vertices)):
            #continue
            # rotate 90 degrees around y axis
            self.vertices[i] = np.array([self.vertices[i][2],self.vertices[i][1],-1*self.vertices[i][0]])
            # rotate vertex normal 90degrees around y axis
            self.vertex_normals[i] = np.array([self.vertex_normals[i][2],self.vertex_normals[i][1],-1*self.vertex_normals[i][0]])
            # rotate -90 degrees around x axis
            self.vertices[i] = np.array([self.vertices[i][0],-1*self.vertices[i][2],self.vertices[i][1]])
            # rotate vertex normal -90degrees around x axis
            self.vertex_normals[i] = np.array([self.vertex_normals[i][0],-1*self.vertex_normals[i][2],self.vertex_normals[i][1]])

        #print(self.bounding_box_vertices[0])

        self.gl_list_generated = False
        #self.generate_gl_list()

    def make_box(self, box_coords):
        from_z = box_coords[0]
        to_z = box_coords[1]
        from_y = box_coords[2]
        to_y = box_coords[3]
        from_x = box_coords[4]
        to_x = box_coords[5]

        box_vertex = np.array([
            [from_z, from_y, from_x],
            [to_z, from_y, from_x],
            [from_z, to_y, from_x],
            [to_z, to_y, from_x],
            [from_z, from_y, to_x],
            [to_z, from_y, to_x],
            [from_z, to_y, to_x],
            [to_z, to_y, to_x]
        ], dtype=np.float64)

        box_edges = [
            [0,1],
            [0,2],
            [0,4],
            [1,3],
            [1,5],
            [2,3],
            [2,6],
            [3,7],
            [4,5],
            [4,6],
            [5,7],
            [6,7]
        ]
        return box_vertex, box_edges

    def set_bounding_box(self, bounding_box):
        self.bounding_box = np.array(bounding_box, dtype=np.float64)
        self.bounding_box_vertices, self.bounding_box_edges = self.make_box(self.bounding_box)
        #print("bounding_box_vertices:", self.bounding_box_vertices)
    
    def set_curr_slice(self, curr_slice):
        self.curr_slice = curr_slice
        self.curr_slice_vertices = np.array([
            [self.curr_slice, self.bounding_box_vertices[0][1], self.bounding_box_vertices[0][2]],
            [self.curr_slice, self.bounding_box_vertices[2][1], self.bounding_box_vertices[2][2]],
            [self.curr_slice, self.bounding_box_vertices[6][1], self.bounding_box_vertices[6][2]],
            [self.curr_slice, self.bounding_box_vertices[4][1], self.bounding_box_vertices[4][2]]
        ], dtype=np.float64)
        #print("curr_slice_vertices:", self.curr_slice_vertices)

    def set_roi_box(self, roi_box):
        self.roi_box = np.array(roi_box, dtype=np.float64)
        self.roi_box_vertices, self.roi_box_edges = self.make_box(self.roi_box)

    def adjust_vertices(self):
        self.bounding_box_vertices -= self.roi_box_vertices[0]
        self.curr_slice_vertices -= self.roi_box_vertices[0]
        self.roi_box_vertices -= self.roi_box_vertices[0]
        #print("curr_slice_vertices 3:", self.curr_slice_vertices)
        if self.bounding_box is not None:
            self.bounding_box /= 10.0
            self.bounding_box_vertices /= 10.0
        if self.roi_box is not None:
            self.roi_box /= 10.0
            self.roi_box_vertices /= 10.0
        if self.curr_slice is not None:
            self.curr_slice_vertices /= 10.0

        if self.bounding_box is not None:
            #print("bounding box:", self.bounding_box.shape, average_coordinates.shape)
            #self.bounding_box -= average_coordinates
            self.bounding_box_vertices -= self.average_coordinates
        if self.roi_box is not None:
            #self.roi_box -= average_coordinates
            self.roi_box_vertices -= self.average_coordinates
        if self.curr_slice is not None:
            self.curr_slice_vertices -= self.average_coordinates

        # rotate bounding box and roi box
        for i in range(len(self.bounding_box_vertices)):
            self.bounding_box_vertices[i] = np.array([self.bounding_box_vertices[i][2],self.bounding_box_vertices[i][1],-1*self.bounding_box_vertices[i][0]])
            self.bounding_box_vertices[i] = np.array([self.bounding_box_vertices[i][0],-1*self.bounding_box_vertices[i][2],self.bounding_box_vertices[i][1]])
            if self.roi_box is not None:
                self.roi_box_vertices[i] = np.array([self.roi_box_vertices[i][2],self.roi_box_vertices[i][1],-1*self.roi_box_vertices[i][0]])
                self.roi_box_vertices[i] = np.array([self.roi_box_vertices[i][0],-1*self.roi_box_vertices[i][2],self.roi_box_vertices[i][1]])
                pass
        for i in range(len(self.curr_slice_vertices)):
            self.curr_slice_vertices[i] = np.array([self.curr_slice_vertices[i][2],self.curr_slice_vertices[i][1],-1*self.curr_slice_vertices[i][0]])
            self.curr_slice_vertices[i] = np.array([self.curr_slice_vertices[i][0],-1*self.curr_slice_vertices[i][2],self.curr_slice_vertices[i][1]])


    def set_volume(self, volume):
        self.volume = volume
        #print(self.volume.shape)
        max_len = max(self.volume.shape)
        # set max length to 100
        scale_factors = 50.0/max_len

        # Use scipy's zoom function for interpolation
        self.volume = ndimage.zoom(self.volume, scale_factors, order=1)
        if self.bounding_box is not None:
            self.bounding_box *= scale_factors
            self.bounding_box_vertices *= scale_factors
        if self.roi_box is not None:
            self.roi_box *= scale_factors
            self.roi_box_vertices *= scale_factors
        if self.curr_slice is not None:
            self.curr_slice_vertices *= scale_factors
        #print("curr_slice_vertices 2:", self.curr_slice_vertices)

        #print("volume shape:", self.volume.shape)
        #print("bounding box:", self.bouding_box)
        #print("roi box:", self.roi_box)
        #print(self.volume.shape)

    def set_isovalue(self, isovalue):
        self.isovalue = isovalue

    def read_images_from_folder(self,folder):
        images = []
        for filename in os.listdir(folder):
            # read images using Pillow
            img = Image.open(os.path.join(folder,filename))
            #img = cv2.imread(os.path.join(folder,filename),0)
            if img is not None:
                images.append(np.array(img))
        return np.array(images)

    def timeout(self):
        #print("timeout, auto_rotate:", self.auto_rotate)
        if self.auto_rotate == False:
            #print "no rotate"
            return
        if self.is_dragging:
            #print "dragging"
            return

        self.rotate_x += 1
        self.updateGL()


    def mousePressEvent(self, event):
        # left button: rotate
        # right button: zoom
        # middle button: pan

        self.down_x = event.x()
        self.down_y = event.y()
        #print("down_x:", self.down_x, "down_y:", self.down_y)
        if event.buttons() == Qt.LeftButton:
            self.view_mode = ROTATE_MODE
        elif event.buttons() == Qt.RightButton:
            self.view_mode = ZOOM_MODE
        elif event.buttons() == Qt.MiddleButton:
            self.view_mode = PAN_MODE

    def mouseReleaseEvent(self, event):
        import datetime
        self.is_dragging = False
        self.curr_x = event.x()
        self.curr_y = event.y()
        #print("curr_x:", self.curr_x, "curr_y:", self.curr_y)
        if event.button() == Qt.LeftButton:
                self.rotate_x += self.temp_rotate_x
                self.rotate_y += self.temp_rotate_y
                if False: #self.threed_model is not None:
                    #print("rotate_x:", self.rotate_x, "rotate_y:", self.rotate_y)
                    #print("1:",datetime.datetime.now())
                    if self.show_model == True:
                        apply_rotation_to_vertex = True
                    else:
                        apply_rotation_to_vertex = False
                    self.threed_model.rotate(math.radians(self.rotate_x),math.radians(self.rotate_y),apply_rotation_to_vertex)
                    #print("2:",datetime.datetime.now())
                    #self.threed_model.rotate_3d(math.radians(-1*self.rotate_x),'Y')
                    #self.threed_model.rotate_3d(math.radians(self.rotate_y),'X')
                    if self.show_model == True:
                        self.threed_model.generate()
                    #print("3:",datetime.datetime.now())
                #print( "test_obj vert 1 after rotation:", self.test_obj.vertices[0])
                #self.rotate_x = 0
                self.rotate_y = 0
                self.temp_rotate_x = 0
                self.temp_rotate_y = 0
        elif event.button() == Qt.RightButton:
            self.dolly += self.temp_dolly 
            self.temp_dolly = 0
        elif event.button() == Qt.MiddleButton:
            self.pan_x += self.temp_pan_x
            self.pan_y += self.temp_pan_y
            self.temp_pan_x = 0
            self.temp_pan_y = 0
        self.view_mode = VIEW_MODE
        self.updateGL()
        #self.parent.update_status()

    def mouseMoveEvent(self, event):
        #@print("mouse move event",event)
        self.curr_x = event.x()
        self.curr_y = event.y()
        #print("curr_x:", self.curr_x, "curr_y:", self.curr_y)

        if event.buttons() == Qt.LeftButton and self.view_mode == ROTATE_MODE:
            self.is_dragging = True
            self.temp_rotate_x = self.curr_x - self.down_x
            self.temp_rotate_y = self.curr_y - self.down_y
        elif event.buttons() == Qt.RightButton and self.view_mode == ZOOM_MODE:
            self.is_dragging = True
            self.temp_dolly = ( self.curr_y - self.down_y ) / 100.0
        elif event.buttons() == Qt.MiddleButton and self.view_mode == PAN_MODE:
            self.is_dragging = True
            self.temp_pan_x = self.curr_x - self.down_x
            self.temp_pan_y = self.curr_y - self.down_y
        self.updateGL()

    def wheelEvent(self, event):
        #print("wheel event", event.angleDelta().y())
        self.dolly -= event.angleDelta().y() / 240.0
        self.updateGL()


    def initializeGL(self):
        #print("initGL")
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_COLOR_MATERIAL)
        glShadeModel(GL_SMOOTH)

        glEnable(GL_LIGHTING)
        glEnable(GL_LIGHT0)

        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

    def resizeGL(self, width, height):
        #print("resizeGL")
        glViewport(0, 0, width, height)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, (width / height), 0.1, 50.0)
        glMatrixMode(GL_MODELVIEW)

    def draw_box(self, box_vertices, box_edges, color=[1.0, 0.0, 0.0]):
        glColor3f(color[0], color[1], color[2])
        v = box_vertices
        glBegin(GL_LINES)
        for e in box_edges:
            for idx in e:
                glVertex3fv(v[idx])
        glEnd()


    def paintGL(self):
        #print("paintGL")
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()


        glMatrixMode(GL_MODELVIEW)
        
        glClearColor(0.94,0.94,0.94, 1)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        glEnable(GL_POINT_SMOOTH)
        glEnable(GL_LIGHTING)


        # Set camera position and view
        gluLookAt(0, 0, 5, 0, 0, 0, 0, 1, 0)

        glTranslatef(0, 0, -5.0 + self.dolly + self.temp_dolly)   # x, y, z 
        glTranslatef((self.pan_x + self.temp_pan_x)/100.0, (self.pan_y + self.temp_pan_y)/-100.0, 0.0)

        # rotate viewpoint
        glRotatef(self.rotate_y + self.temp_rotate_y, 1.0, 0.0, 0.0)
        glRotatef(self.rotate_x + self.temp_rotate_x, 0.0, 1.0, 0.0)

        if len(self.triangles) == 0:
            return

        glClearColor(0.2,0.2,0.2, 1)
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

        ''' render bounding box and roi box '''
        glDisable(GL_LIGHTING)
        # render bounding box
        if self.bounding_box is not None:
            glLineWidth(1)
            self.draw_box(self.bounding_box_vertices, self.bounding_box_edges, color=[0.0, 0.0, 1.0])
        # render roi box
        
        if self.roi_box is not None:
            #print("roi box:", self.roi_box_vertices)
            #print("bounding box:", self.bounding_box_vertices)
            #print("check", self.roi_box_vertices == self.bounding_box_vertices)
            if not (self.roi_box_vertices == self.bounding_box_vertices).all():
                glLineWidth(2)
                self.draw_box(self.roi_box_vertices, self.roi_box_edges, color=[1.0, 0.0, 0.0])
        glEnable(GL_LIGHTING)

        ''' render 3d model '''
        glColor3f(0.0, 1.0, 0.0)
        if self.gl_list_generated == False:
            self.generate_gl_list()

        self.render_gl_list()


        glColor4f(0.0, 1.0, 0.0, 0.5) 

        glBegin(GL_QUADS)
        for vertex in self.curr_slice_vertices:
            #glNormal3fv(self.vertex_normals[0])
            glVertex3fv(vertex)
            #print(vertex)
        glEnd()


        return

    def render_gl_list(self):
        if self.gl_list_generated == False:
            return
        #print("render", self, self.gl_list)
        glCallList(self.gl_list)
        return

    def generate_gl_list(self):
        self.gl_list = glGenLists(1)
        glNewList(self.gl_list, GL_COMPILE)

        # Render the 3D surface
        glBegin(GL_TRIANGLES)
        
        for triangle in self.triangles:
            for vertex in triangle:
                glNormal3fv(self.vertex_normals[vertex])
                glVertex3fv(self.vertices[vertex])
        glEnd()
        glEndList()
        self.gl_list_generated = True


class PreferencesDialog(QDialog):
    '''
    PreferencesDialog shows preferences.

    Args:
        None

    Attributes:
        well..
    '''
    def __init__(self,parent):
        super().__init__()
        self.parent = parent
        self.m_app = QApplication.instance()
        #self.m_app.remember_geometry = True
        #self.m_app.remember_directory = True
        #self.m_app.language = "en"
        #self.m_app.default_directory = "."

        self.rbRememberGeometryYes = QRadioButton(self.tr("Yes"))
        self.rbRememberGeometryYes.setChecked(self.m_app.remember_geometry)
        self.rbRememberGeometryYes.clicked.connect(self.on_rbRememberGeometryYes_clicked)
        self.rbRememberGeometryNo = QRadioButton(self.tr("No"))
        self.rbRememberGeometryNo.setChecked(not self.m_app.remember_geometry)
        self.rbRememberGeometryNo.clicked.connect(self.on_rbRememberGeometryNo_clicked)

        self.rbRememberDirectoryYes = QRadioButton(self.tr("Yes"))
        self.rbRememberDirectoryYes.setChecked(self.m_app.remember_directory)
        self.rbRememberDirectoryYes.clicked.connect(self.on_rbRememberDirectoryYes_clicked)
        self.rbRememberDirectoryNo = QRadioButton(self.tr("No"))
        self.rbRememberDirectoryNo.setChecked(not self.m_app.remember_directory)
        self.rbRememberDirectoryNo.clicked.connect(self.on_rbRememberDirectoryNo_clicked)

        self.gbRememberGeometry = QGroupBox()
        self.gbRememberGeometry.setLayout(QHBoxLayout())
        self.gbRememberGeometry.layout().addWidget(self.rbRememberGeometryYes)
        self.gbRememberGeometry.layout().addWidget(self.rbRememberGeometryNo)

        self.gbRememberDirectory = QGroupBox()
        self.gbRememberDirectory.setLayout(QHBoxLayout())
        self.gbRememberDirectory.layout().addWidget(self.rbRememberDirectoryYes)
        self.gbRememberDirectory.layout().addWidget(self.rbRememberDirectoryNo)

        self.comboLang = QComboBox()
        self.comboLang.addItem(self.tr("English"))
        self.comboLang.addItem(self.tr("Korean"))
        self.comboLang.currentIndexChanged.connect(self.comboLangIndexChanged)

        self.main_layout = QVBoxLayout()
        self.form_layout = QFormLayout()
        self.setLayout(self.main_layout)
        self.form_layout.addRow(self.tr("Remember Geometry"), self.gbRememberGeometry)
        self.form_layout.addRow(self.tr("Remember Directory"), self.gbRememberDirectory)
        self.form_layout.addRow(self.tr("Language"), self.comboLang)
        self.button_layout = QHBoxLayout()
        self.btnOK = QPushButton(self.tr("OK"))
        self.btnOK.clicked.connect(self.on_btnOK_clicked)
        self.btnCancel = QPushButton(self.tr("Cancel"))
        self.btnCancel.clicked.connect(self.on_btnCancel_clicked)
        self.button_layout.addWidget(self.btnOK)
        self.button_layout.addWidget(self.btnCancel)
        self.main_layout.addLayout(self.form_layout)
        self.main_layout.addLayout(self.button_layout)
        self.setWindowTitle(self.tr("CTHarvester - Preferences"))
        self.setGeometry(QRect(100, 100, 320, 180))
        self.move(self.parent.pos()+QPoint(100,100))

        self.read_settings()

    def on_btnOK_clicked(self):
        self.save_settings()
        self.close()

    def on_btnCancel_clicked(self):
        self.close()

    def on_rbRememberGeometryYes_clicked(self):
        self.m_app.remember_geometry = True

    def on_rbRememberGeometryNo_clicked(self):
        self.m_app.remember_geometry = False

    def on_rbRememberDirectoryYes_clicked(self):
        self.m_app.remember_directory = True

    def on_rbRememberDirectoryNo_clicked(self):
        self.m_app.remember_directory = False

    def comboLangIndexChanged(self, index):
        if index == 0:
            self.m_app.language = "en"
        elif index == 1:
            self.m_app.language = "ko"
        #print("self.language:", self.m_app.language)

    def update_language(self):
        #print("update_language", self.m_app.language)
        translator = QTranslator()
        translator.load(resource_path('CTHarvester_{}.qm').format(self.m_app.language))
        self.m_app.installTranslator(translator)
        
        self.rbRememberGeometryYes.setText(self.tr("Yes"))
        self.rbRememberGeometryNo.setText(self.tr("No"))
        self.rbRememberDirectoryYes.setText(self.tr("Yes"))
        self.rbRememberDirectoryNo.setText(self.tr("No"))
        self.gbRememberGeometry.setTitle("")
        self.gbRememberDirectory.setTitle("")
        self.comboLang.setItemText(0, self.tr("English"))
        self.comboLang.setItemText(1, self.tr("Korean"))
        self.btnOK.setText(self.tr("OK"))
        self.btnCancel.setText(self.tr("Cancel"))
        self.form_layout.labelForField(self.gbRememberGeometry).setText(self.tr("Remember Geometry"))
        self.form_layout.labelForField(self.gbRememberDirectory).setText(self.tr("Remember Directory"))
        self.form_layout.labelForField(self.comboLang).setText(self.tr("Language"))
        self.setWindowTitle(self.tr("CTHarvester - Preferences"))
        self.parent.update_language()
        self.parent.update_status()

    def read_settings(self):
        self.m_app.remember_geometry = value_to_bool(self.m_app.settings.value("Remember geometry", True))
        self.m_app.remember_directory = value_to_bool(self.m_app.settings.value("Remember directory", True))
        self.m_app.language = self.m_app.settings.value("Language", "en")
        #self.m_app.default_directory = self.m_app.settings.value("Default directory", ".")
        #print("self.language:", self.m_app.language
        #        , "self.remember_geometry:", self.m_app.remember_geometry
        #        , "self.remember_directory:", self.m_app.remember_directory
        #        , "self.default_directory:", self.m_app.default_directory)

        self.rbRememberGeometryYes.setChecked(self.m_app.remember_geometry)
        self.rbRememberGeometryNo.setChecked(not self.m_app.remember_geometry)
        self.rbRememberDirectoryYes.setChecked(self.m_app.remember_directory)
        self.rbRememberDirectoryNo.setChecked(not self.m_app.remember_directory)

        if self.m_app.language == "en":
            self.comboLang.setCurrentIndex(0)
        elif self.m_app.language == "ko":
            self.comboLang.setCurrentIndex(1)
        self.update_language()

    def save_settings(self):
        self.m_app.settings.setValue("Remember geometry", self.m_app.remember_geometry)
        self.m_app.settings.setValue("Remember directory", self.m_app.remember_directory)
        self.m_app.settings.setValue("Language", self.m_app.language)
        self.update_language()

class ProgressDialog(QDialog):
    def __init__(self,parent):
        super().__init__()
        #self.setupUi(self)
        #self.setGeometry(200, 250, 400, 250)
        self.setWindowTitle(self.tr("CTHarvester - Progress Dialog"))
        self.parent = parent
        self.m_app = QApplication.instance()
        self.setGeometry(QRect(100, 100, 320, 180))
        self.move(self.parent.pos()+QPoint(100,100))

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(50,50, 50, 50)

        self.lbl_text = QLabel(self)
        #self.lbl_text.setGeometry(50, 50, 320, 80)
        #self.pb_progress = QProgressBar(self)
        self.pb_progress = QProgressBar(self)
        #self.pb_progress.setGeometry(50, 150, 320, 40)
        self.pb_progress.setValue(0)
        self.stop_progress = False
        self.btnStop = QPushButton(self)
        #self.btnStop.setGeometry(175, 200, 50, 30)
        self.btnStop.setText(self.tr("Stop"))
        self.btnStop.clicked.connect(self.set_stop_progress)
        self.btnStop.hide()
        self.layout.addWidget(self.lbl_text)
        self.layout.addWidget(self.pb_progress)
        #self.layout.addWidget(self.btnStop)
        self.setLayout(self.layout)
        #self.update_language()

    def set_stop_progress(self):
        self.stop_progress = True

    def set_progress_text(self,text_format):
        self.text_format = text_format

    def set_max_value(self,max_value):
        self.max_value = max_value

    def set_curr_value(self,curr_value):
        self.curr_value = curr_value
        self.pb_progress.setValue(int((self.curr_value/float(self.max_value))*100))
        self.lbl_text.setText(self.text_format.format(self.curr_value, self.max_value))
        #self.lbl_text.setText(label_text)
        self.update()
        QApplication.processEvents()

    def update_language(self):
        #print("update_language", self.m_app.language)
        translator = QTranslator()
        translator.load(resource_path('CTHarvester_{}.qm').format(self.m_app.language))
        self.m_app.installTranslator(translator)
        
        self.setWindowTitle(self.tr("CTHarvester - Progress Dialog"))
        self.btnStop.setText(self.tr("Stop"))


class ObjectViewer2D(QLabel):
    def __init__(self, widget):
        super(ObjectViewer2D, self).__init__(widget)
        self.setMinimumSize(512,512)
        self.image_canvas_ratio = 1.0
        self.scale = 1.0
        self.mouse_down_x = 0
        self.mouse_down_y = 0
        self.mouse_curr_x = 0
        self.mouse_curr_y = 0
        self.edit_mode = MODE['ADD_BOX']
        self.orig_pixmap = None
        self.curr_pixmap = None
        self.distance_threshold = self._2imgx(5)
        #print("distance_threshold:", self.distance_threshold)
        self.setMouseTracking(True)
        self.object_dialog = None
        self.top_idx = -1
        self.bottom_idx = -1
        self.curr_idx = 0
        self.move_x = 0
        self.move_y = 0
        self.threed_view = None
        self.isovalue = 60
        self.reset_crop()

    def set_isovalue(self, isovalue):
        self.isovalue = isovalue
        self.update()

    def set_threed_view(self, threed_view):
        self.threed_view = threed_view

    def reset_crop(self):
        self.crop_from_x = -1
        self.crop_from_y = -1
        self.crop_to_x = -1
        self.crop_to_y = -1
        self.temp_x1 = -1
        self.temp_y1 = -1
        self.temp_x2 = -1
        self.temp_y2 = -1
        self.edit_x1 = False
        self.edit_x2 = False
        self.edit_y1 = False
        self.edit_y2 = False
        self.canvas_box = None

    def _2canx(self, coord):
        return round((float(coord) / self.image_canvas_ratio) * self.scale)
    def _2cany(self, coord):
        return round((float(coord) / self.image_canvas_ratio) * self.scale)
    def _2imgx(self, coord):
        return round(((float(coord)) / self.scale) * self.image_canvas_ratio)
    def _2imgy(self, coord):
        return round(((float(coord)) / self.scale) * self.image_canvas_ratio)

    def set_mode(self, mode):
        self.edit_mode = mode
        if self.edit_mode == MODE['ADD_BOX']:
            self.setCursor(Qt.CrossCursor)
        elif self.edit_mode in [ MODE['MOVE_BOX'], MODE['MOVE_BOX_READY'], MODE['MOVE_BOX_PROGRESS'] ]:
            self.setCursor(Qt.OpenHandCursor)
        elif self.edit_mode in [ MODE['EDIT_BOX'], MODE['EDIT_BOX_READY'], MODE['EDIT_BOX_PROGRESS'] ]:
            pass
        else:
            self.setCursor(Qt.ArrowCursor)

    def distance_check(self, x, y):
        x = self._2imgx(x)
        y = self._2imgy(y)
        if self.crop_from_x - self.distance_threshold >= x or self.crop_to_x + self.distance_threshold <= x or self.crop_from_y - self.distance_threshold >= y or self.crop_to_y + self.distance_threshold <= y:
            self.edit_x1 = False
            self.edit_x2 = False
            self.edit_y1 = False
            self.edit_y2 = False
            self.inside_box = False
        else:
            if self.crop_from_x + self.distance_threshold <= x and self.crop_to_x - self.distance_threshold >= x \
                and self.crop_from_y + self.distance_threshold <= y and self.crop_to_y - self.distance_threshold >= y:
                self.edit_x1 = False
                self.edit_x2 = False
                self.edit_y1 = False
                self.edit_y2 = False
                self.inside_box = True
                #print("move box ready")
            else:
                self.inside_box = False
            if abs(self.crop_from_x - x) <= self.distance_threshold:
                self.edit_x1 = True
            else:
                self.edit_x1 = False
            if abs(self.crop_to_x - x) <= self.distance_threshold:
                self.edit_x2 = True
            else:
                self.edit_x2 = False
            if abs(self.crop_from_y - y) <= self.distance_threshold:
                self.edit_y1 = True
            else:
                self.edit_y1 = False
            if abs(self.crop_to_y - y) <= self.distance_threshold:
                self.edit_y2 = True
            else:
                self.edit_y2 = False
        #print("distance_check", self.crop_from_x, self.crop_to_x, x, self.crop_from_y, self.crop_to_y, y, self.edit_x1, self.edit_x2, self.edit_y1, self.edit_y2)
        self.set_cursor_mode()

    def set_cursor_mode(self):
        if self.edit_x1 and self.edit_y1:
            self.setCursor(Qt.SizeFDiagCursor)
        elif self.edit_x2 and self.edit_y2:
            self.setCursor(Qt.SizeFDiagCursor)
        elif self.edit_x1 and self.edit_y2:
            self.setCursor(Qt.SizeBDiagCursor)
        elif self.edit_x2 and self.edit_y1:
            self.setCursor(Qt.SizeBDiagCursor)
        elif self.edit_x1 or self.edit_x2:
            self.setCursor(Qt.SizeHorCursor)
        elif self.edit_y1 or self.edit_y2:
            self.setCursor(Qt.SizeVerCursor)
        elif self.inside_box:
            self.setCursor(Qt.OpenHandCursor)
        else: 
            self.setCursor(Qt.ArrowCursor)

    def mouseMoveEvent(self, event):
        if self.orig_pixmap is None:
            return
        me = QMouseEvent(event)
        #print("mouseMoveEvent", me.x(), me.y(), self.edit_mode)
        #print(self.crop_from_x, self.crop_from_y, self.crop_to_x, self.crop_to_y)
        if me.buttons() == Qt.LeftButton:
            if self.edit_mode == MODE['ADD_BOX']:
                self.mouse_curr_x = me.x()
                self.mouse_curr_y = me.y()
                self.temp_x2 = self._2imgx(self.mouse_curr_x)
                self.temp_y2 = self._2imgy(self.mouse_curr_y)
                #self.object_dialog.edtStatus.setText("({}, {})-({}, {})".format(self.crop_from_x, self.crop_from_y, self.crop_to_x, self.crop_to_y))
            elif self.edit_mode in [ MODE['EDIT_BOX_PROGRESS'], MODE['MOVE_BOX_PROGRESS'] ]:
                self.mouse_curr_x = me.x()
                self.mouse_curr_y = me.y()
                self.move_x = self.mouse_curr_x - self.mouse_down_x
                self.move_y = self.mouse_curr_y - self.mouse_down_y
                #print("move", self.move_x, self.move_y)
            self.calculate_resize()
        else:
            if self.edit_mode == MODE['EDIT_BOX']:
                self.distance_check(me.x(), me.y())
                if self.edit_x1 or self.edit_x2 or self.edit_y1 or self.edit_y2:
                    self.set_mode(MODE['EDIT_BOX_READY'])
                elif self.inside_box:
                    self.set_mode(MODE['MOVE_BOX_READY'])
            elif self.edit_mode == MODE['EDIT_BOX_READY']:
                self.distance_check(me.x(), me.y())
                if self.edit_x1 or self.edit_x2 or self.edit_y1 or self.edit_y2:
                    pass #self.set_mode(MODE['EDIT_BOX_PROGRESS'])
                elif self.inside_box:
                    self.set_mode(MODE['MOVE_BOX_READY'])
                else:
                    self.set_mode(MODE['EDIT_BOX'])
            elif self.edit_mode == MODE['MOVE_BOX_READY']:
                self.distance_check(me.x(), me.y())
                if self.edit_x1 or self.edit_x2 or self.edit_y1 or self.edit_y2:
                    self.set_mode(MODE['EDIT_BOX_READY'])
                elif self.inside_box == False:
                    self.set_mode(MODE['EDIT_BOX'])
        self.object_dialog.update_status()
        self.repaint()

    def mousePressEvent(self, event):
        if self.orig_pixmap is None:
            return
        me = QMouseEvent(event)
        #print("mousePressEvent", me.x(), me.y(),self.edit_mode)
        #print(self.crop_from_x, self.crop_from_y, self.crop_to_x, self.crop_to_y)
        if me.button() == Qt.LeftButton:
            #if self.object_dialog is None:
            #    return
            if self.edit_mode == MODE['ADD_BOX'] or self.edit_mode == MODE['EDIT_BOX']:
                self.set_mode(MODE['ADD_BOX'])
                img_x = self._2imgx(me.x())
                img_y = self._2imgy(me.y())
                #print("mousePressEvent", img_x, img_y)
                if img_x < 0 or img_x > self.orig_pixmap.width() or img_y < 0 or img_y > self.orig_pixmap.height():
                    return
                self.temp_x1 = img_x
                self.temp_y1 = img_y
                self.temp_x2 = img_x
                self.temp_y2 = img_y
            elif self.edit_mode == MODE['EDIT_BOX_READY']:
                self.mouse_down_x = me.x()
                self.mouse_down_y = me.y()
                self.move_x = 0
                self.move_y = 0
                self.temp_x1 = self.crop_from_x
                self.temp_y1 = self.crop_from_y
                self.temp_x2 = self.crop_to_x
                self.temp_y2 = self.crop_to_y
                self.set_mode(MODE['EDIT_BOX_PROGRESS'])
            elif self.edit_mode == MODE['MOVE_BOX_READY']:
                self.mouse_down_x = me.x()
                self.mouse_down_y = me.y()
                self.mouse_curr_x = me.x()
                self.mouse_curr_y = me.y()
                self.move_x = 0
                self.move_y = 0
                self.temp_x1 = self.crop_from_x
                self.temp_y1 = self.crop_from_y
                self.temp_x2 = self.crop_to_x
                self.temp_y2 = self.crop_to_y
                self.set_mode(MODE['MOVE_BOX_PROGRESS'])
        self.object_dialog.update_status()
        self.repaint()

    def mouseReleaseEvent(self, ev: QMouseEvent) -> None:
        if self.orig_pixmap is None:
            return
        me = QMouseEvent(ev)
        if self.mouse_down_x == me.x() and self.mouse_down_y == me.y():
            return
        #print("mouseReleaseEvent", me.x(), me.y(),self.edit_mode)
        #print(self.crop_from_x, self.crop_from_y, self.crop_to_x, self.crop_to_y)
        if me.button() == Qt.LeftButton:
            if self.edit_mode == MODE['ADD_BOX']:
                img_x = self._2imgx(self.mouse_curr_x)
                img_y = self._2imgy(self.mouse_curr_y)
                if img_x < 0 or img_x > self.orig_pixmap.width() or img_y < 0 or img_y > self.orig_pixmap.height():
                    return
                self.crop_from_x = min(self.temp_x1, self.temp_x2)
                self.crop_to_x = max(self.temp_x1, self.temp_x2)
                self.crop_from_y = min(self.temp_y1, self.temp_y2)
                self.crop_to_y = max(self.temp_y1, self.temp_y2)
                self.set_mode(MODE['EDIT_BOX'])
            elif self.edit_mode == MODE['EDIT_BOX_PROGRESS']:
                if self.edit_x1:
                    self.crop_from_x = min(self.temp_x1, self.temp_x2) + self._2imgx(self.move_x)
                if self.edit_x2:
                    self.crop_to_x = max(self.temp_x1, self.temp_x2) + self._2imgx(self.move_x)
                if self.edit_y1:
                    self.crop_from_y = min(self.temp_y1, self.temp_y2) + self._2imgy(self.move_y)
                if self.edit_y2:
                    self.crop_to_y = max(self.temp_y1, self.temp_y2) + self._2imgy(self.move_y)
                self.move_x = 0
                self.move_y = 0
                self.set_mode(MODE['EDIT_BOX'])
            elif self.edit_mode == MODE['MOVE_BOX_PROGRESS']:
                self.crop_from_x = self.temp_x1 + self._2imgx(self.move_x)
                self.crop_to_x = self.temp_x2 + self._2imgx(self.move_x)
                self.crop_from_y = self.temp_y1 + self._2imgy(self.move_y)
                self.crop_to_y = self.temp_y2 + self._2imgy(self.move_y)
                self.move_x = 0
                self.move_y = 0
                self.set_mode(MODE['MOVE_BOX_READY'])

            from_x = min(self.crop_from_x, self.crop_to_x)
            to_x = max(self.crop_from_x, self.crop_to_x)
            from_y = min(self.crop_from_y, self.crop_to_y)
            to_y = max(self.crop_from_y, self.crop_to_y)
            self.crop_from_x = from_x
            self.crop_from_y = from_y
            self.crop_to_x = to_x
            self.crop_to_y = to_y
            self.canvas_box = QRect(self._2canx(from_x), self._2cany(from_y), self._2canx(to_x - from_x), self._2cany(to_y - from_y))
            self.calculate_resize()
            self.object_dialog.update_3D_view()
            #self.object_dialog.update_status()

        self.object_dialog.update_status()
        #self.object_dialog.update_3D_view()
        self.repaint()

    def get_crop_area(self, imgxy = False):
        from_x = -1
        to_x = -1
        from_y = -1
        to_y = -1
        if self.edit_mode == MODE['ADD_BOX']:
            from_x = self._2canx(min(self.temp_x1, self.temp_x2))
            to_x = self._2canx(max(self.temp_x1, self.temp_x2))
            from_y = self._2cany(min(self.temp_y1, self.temp_y2))
            to_y = self._2cany(max(self.temp_y1, self.temp_y2))
            #return [from_x, from_y, to_x, to_y]
        elif self.edit_mode in [ MODE['EDIT_BOX_PROGRESS'], MODE['MOVE_BOX_PROGRESS'] ]:
            from_x = self._2canx(min(self.temp_x1, self.temp_x2)) 
            to_x = self._2canx(max(self.temp_x1, self.temp_x2))
            from_y = self._2cany(min(self.temp_y1, self.temp_y2))
            to_y = self._2cany(max(self.temp_y1, self.temp_y2))
            if self.edit_x1 or self.edit_mode == MODE['MOVE_BOX_PROGRESS']:
                from_x += self.move_x
            if self.edit_x2 or self.edit_mode == MODE['MOVE_BOX_PROGRESS']:
                to_x += self.move_x
            if self.edit_y1 or self.edit_mode == MODE['MOVE_BOX_PROGRESS']:
                from_y += self.move_y
            if self.edit_y2 or self.edit_mode == MODE['MOVE_BOX_PROGRESS']:
                to_y += self.move_y
            #return [from_x, from_y, to_x, to_y]
        elif self.crop_from_x > -1:
            from_x = self._2canx(min(self.crop_from_x, self.crop_to_x))
            to_x = self._2canx(max(self.crop_from_x, self.crop_to_x))
            from_y = self._2cany(min(self.crop_from_y, self.crop_to_y))
            to_y = self._2cany(max(self.crop_from_y, self.crop_to_y))

        if imgxy == True:
            #print("imagexy true", from_x, self.orig_pixmap)
            if from_x <= 0 and from_y <= 0 and to_x <= 0 and to_y <= 0 and self.orig_pixmap:
                return [ 0,0,self.orig_pixmap.width(),self.orig_pixmap.height()]
            else:
                return [self._2imgx(from_x), self._2imgy(from_y), self._2imgx(to_x), self._2imgy(to_y)]
        else:
            return [from_x, from_y, to_x, to_y]


    def paintEvent(self, event):
        # fill background with dark gray
        painter = QPainter(self)
        #painter.fillRect(self.rect(), QBrush(QColor()))#as_qt_color(COLOR['BACKGROUND'])))
        if self.curr_pixmap is not None:

            #print("paintEvent", self.curr_pixmap.width(), self.curr_pixmap.height())
            painter.drawPixmap(0,0,self.curr_pixmap)

        if self.curr_idx > self.top_idx or self.curr_idx < self.bottom_idx:
            painter.setPen(QPen(QColor(128,0,0), 2, Qt.DotLine))
        else:
            painter.setPen(QPen(Qt.red, 2, Qt.SolidLine))
        [ x1, y1, x2, y2 ] = self.get_crop_area()
        #print("paintEvent", x1, y1, x2, y2)
        painter.drawRect(x1, y1, x2 - x1, y2 - y1)

    def apply_threshold_and_colorize(self,qt_pixmap, threshold, color=np.array([0, 255, 0], dtype=np.uint8)):
        #print("apply_threshold_and_colorize", qt_pixmap.width(), qt_pixmap.height())
        # Convert the QPixmap to a NumPy array
        qt_image = qt_pixmap.toImage()
        
        # Convert the QImage to a NumPy array
        width = qt_image.width()
        height = qt_image.height()
        buffer = qt_image.bits()
        buffer.setsize(qt_image.byteCount())
        qt_image_array = np.frombuffer(buffer, dtype=np.uint8).reshape((height, width, 4))
        #print("qt_image_array", qt_image_array.shape, qt_image_array.dtype)
        
        # Extract the alpha channel (if present)
        if qt_image_array.shape[2] == 4:
            qt_image_array = qt_image_array[:, :, :3]  # Remove the alpha channel

        color = np.array([0, 255, 0], dtype=np.uint8)

        # ... (load or create image_array)
        #image_array = self.convert_qt_pixmap_to_ndarray(qt_pixmap)
        #print("image_array", qt_image_array.shape)
        #print("image array[10,10]", qt_image_array[10,10,:])

        # Check the dtype of image_array
        if qt_image_array.dtype != np.uint8:
            raise ValueError("image_array should have dtype np.uint8")

        # Check the threshold value (example threshold)
        threshold = self.isovalue
        if not 0 <= threshold <= 255:
            raise ValueError("Threshold should be in the range 0-255")
        
        [ x1, y1, x2, y2 ] = self.get_crop_area()
        #print("apply_threshold_and_colorize", x1, y1, x2, y2)
        if x1 == x2 == y1 == y2 == 0:
            # whole pixmap is selected
            x1, x2, y1, y2 = 0, qt_image_array.shape[1], 0, qt_image_array.shape[0]


        region_mask = (qt_image_array[y1:y2+1, x1:x2+1, 0] > threshold)

        # Apply the threshold and colorize
        qt_image_array[y1:y2+1, x1:x2+1][region_mask] = color
        #qt_image_array[qt_image_array[:, :, 0] > threshold] = color

        # Convert the NumPy array back to a QPixmap
        height, width, channel = qt_image_array.shape
        bytes_per_line = 3 * width
        qt_image = QImage(np.copy(qt_image_array.data), width, height, bytes_per_line, QImage.Format_RGB888)
        
        # Convert the QImage to a QPixmap
        modified_pixmap = QPixmap.fromImage(qt_image)

        #print("modified_pixmap", modified_pixmap.width(), modified_pixmap.height())
        
        return modified_pixmap

    def set_image(self,file_path):
        #print("set_image", file_path)
        # check if file exists
        if not os.path.exists(file_path):
            #print("file not exists:", file_path)
            self.curr_pixmap = None
            self.orig_pixmap = None
            self.crop_from_x = -1
            self.crop_from_y = -1
            self.crop_to_x = -1
            self.crop_to_y = -1
            self.canvas_box = None
            return
        self.fullpath = file_path
        self.curr_pixmap = self.orig_pixmap = QPixmap(file_path)

        self.setPixmap(self.curr_pixmap)
        self.calculate_resize()
        if self.canvas_box:
            self.crop_from_x = self._2imgx(self.canvas_box.x())
            self.crop_from_y = self._2imgy(self.canvas_box.y())
            self.crop_to_x = self._2imgx(self.canvas_box.x() + self.canvas_box.width())
            self.crop_to_y = self._2imgy(self.canvas_box.y() + self.canvas_box.height())
    def set_top_idx(self, top_idx):
        self.top_idx = top_idx
    def set_curr_idx(self, curr_idx):
        self.curr_idx = curr_idx
        #print("set_curr_idx", curr_idx, self.max_idx, self.min_idx)
        #print("set_curr_idx", )
    def set_bottom_idx(self, bottom_idx):
        self.bottom_idx = bottom_idx

    def calculate_resize(self):
        #print("objectviewer calculate resize")
        if self.orig_pixmap is not None:
            self.distance_threshold = self._2imgx(DISTANCE_THRESHOLD)
            #print("distance_threshold:", self.distance_threshold)
            self.orig_width = self.orig_pixmap.width()
            self.orig_height = self.orig_pixmap.height()
            image_wh_ratio = self.orig_width / self.orig_height
            label_wh_ratio = self.width() / self.height()
            if image_wh_ratio > label_wh_ratio:
                self.image_canvas_ratio = self.orig_width / self.width()
            else:
                self.image_canvas_ratio = self.orig_height / self.height()
            #print("calculate_resize", self.orig_width, self.orig_height, self.width(), self.height(), self.image_canvas_ratio, self.scale)

            self.curr_pixmap = self.orig_pixmap.scaled(int(self.orig_width*self.scale/self.image_canvas_ratio),int(self.orig_width*self.scale/self.image_canvas_ratio), Qt.KeepAspectRatio)
            #print("curr_pixmap", self.curr_pixmap.width(), self.curr_pixmap.height())
            # if between bottom_idx and top_idx, apply threshold
            #print("isovalue", self.isovalue, self.curr_idx, self.bottom_idx, self.top_idx)
            if self.isovalue > 0 and self.curr_idx >= self.bottom_idx and self.curr_idx <= self.top_idx:
                #print("getting new pixmap")
                self.curr_pixmap = self.apply_threshold_and_colorize(self.curr_pixmap, self.isovalue)
                #pass

    def resizeEvent(self, a0: QResizeEvent) -> None:
        self.calculate_resize()
        if self.canvas_box:
            self.canvas_box = QRect(self._2canx(self.crop_from_x), self._2cany(self.crop_from_y), self._2canx(self.crop_to_x - self.crop_from_x), self._2cany(self.crop_to_y - self.crop_from_y))
        self.threed_view.resize_self()
        return super().resizeEvent(a0)


class CTHarvesterMainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.m_app = QApplication.instance()

        self.setWindowIcon(QIcon(resource_path('CTHarvester_48_2.png')))
        self.setWindowTitle("{} v{}".format(self.tr("CT Harvester"), PROGRAM_VERSION))
        self.setGeometry(QRect(100, 100, 600, 550))
        self.settings_hash = {}
        self.level_info = []
        self.curr_level_idx = 0
        self.prev_level_idx = 0
        self.default_directory = "."
        self.read_settings()

        margin = QMargins(11,0,11,0)

        # add file open dialog
        self.dirname_layout = QHBoxLayout()
        self.dirname_widget = QWidget()
        self.btnOpenDir = QPushButton(self.tr("Open Directory"))
        self.btnOpenDir.clicked.connect(self.open_dir)
        self.edtDirname = QLineEdit()
        self.edtDirname.setReadOnly(True)
        self.edtDirname.setText("")
        self.edtDirname.setPlaceholderText(self.tr("Select directory to load CT data"))
        self.edtDirname.setMinimumWidth(400)
        #self.edtDirname.setMaximumWidth(400)
        self.edtDirname.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.dirname_layout.addWidget(self.edtDirname,stretch=1)
        self.dirname_layout.addWidget(self.btnOpenDir,stretch=0)
        self.dirname_widget.setLayout(self.dirname_layout)
        #self.dirname_layout.setSpacing(0)
        self.dirname_layout.setContentsMargins(margin)

        self.image_info_layout = QHBoxLayout()
        self.image_info_widget = QWidget()
        self.edtImageDimension = QLineEdit()
        self.edtImageDimension.setReadOnly(True)
        self.edtImageDimension.setText("")
        self.edtNumImages = QLineEdit()
        self.edtNumImages.setReadOnly(True)
        self.edtNumImages.setText("")
        self.lblSize01 = QLabel(self.tr("Size"))
        self.lblCount01 = QLabel(self.tr("Count"))
        self.image_info_layout.addWidget(self.lblSize01)
        self.image_info_layout.addWidget(self.edtImageDimension)
        self.image_info_layout.addWidget(self.lblCount01)
        self.image_info_layout.addWidget(self.edtNumImages)
        self.image_info_widget.setLayout(self.image_info_layout)

        self.image_layout = QHBoxLayout()
        self.image_label = QLabel()
        self.image_label.setPixmap(QPixmap("D:/CT/CO-1/CO-1_Rec/small/CO-1__rec00000001.bmp"))
        self.image_layout.addWidget(self.image_label)
        self.lstFileList = QListWidget()
        self.lstFileList.setAlternatingRowColors(True)
        self.lstFileList.setSelectionMode(QAbstractItemView.SingleSelection)
        self.lstFileList.setDragDropMode(QAbstractItemView.NoDragDrop)
        self.lstFileList.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.lstFileList.itemSelectionChanged.connect(self.lstFileListSelectionChanged)

        self.crop_layout = QHBoxLayout()
        self.crop_widget = QWidget()
        self.btnFromImage = QPushButton("From >")
        #self.btnFromImage.clicked.connect(self.set_from_image)
        self.edtFromImage = QLineEdit()
        self.btnToImage = QPushButton("To >")
        #self.btnToImage.clicked.connect(self.set_to_image)
        self.edtToImage = QLineEdit()
        self.btnCrop = QPushButton("Reset")
        #self.btnCrop.clicked.connect(self.set_crop)

        self.crop_layout.addWidget(self.btnFromImage)
        self.crop_layout.addWidget(self.edtFromImage)
        self.crop_layout.addWidget(self.btnToImage)
        self.crop_layout.addWidget(self.edtToImage)
        self.crop_layout.addWidget(self.btnCrop)
        self.crop_widget.setLayout(self.crop_layout)
        
        self.image_layout.addWidget(self.lstFileList)
        self.image_widget = QWidget()
        self.image_widget.setLayout(self.image_layout)

        self.btnCreateThumbnail = QPushButton("Prepare View")
        self.btnCreateThumbnail.clicked.connect(self.create_thumbnail)


        self.left_layout = QVBoxLayout()
        self.left_widget = QWidget()
        self.left_widget.setLayout(self.left_layout)
        #self.left_layout.addWidget(self.dirname_widget)
        self.left_layout.addWidget(self.image_info_widget)
        self.left_layout.addWidget(self.image_widget)
        self.left_layout.addWidget(self.btnCreateThumbnail)
        #self.left_layout.addWidget(self.crop_widget)

        self.lblLevel = QLabel(self.tr("Level"))
        self.comboLevel = QComboBox()
        self.comboLevel.currentIndexChanged.connect(self.comboLevelIndexChanged)

        self.image_info_layout2 = QHBoxLayout()
        self.image_info_widget2 = QWidget()
        
        self.edtImageDimension2 = QLineEdit()
        self.edtImageDimension2.setReadOnly(True)
        self.edtImageDimension2.setText("")
        self.edtNumImages2 = QLineEdit()
        self.edtNumImages2.setReadOnly(True)
        self.edtNumImages2.setText("")
        self.image_info_layout2.addWidget(self.lblLevel)
        self.image_info_layout2.addWidget(self.comboLevel)
        self.lblSize02 = QLabel(self.tr("Size"))
        self.lblCount02 = QLabel(self.tr("Count")) 
        self.image_info_layout2.addWidget(self.lblSize02)
        self.image_info_layout2.addWidget(self.edtImageDimension2)
        self.image_info_layout2.addWidget(self.lblCount02)
        self.image_info_layout2.addWidget(self.edtNumImages2)
        self.image_info_widget2.setLayout(self.image_info_layout2)
        #self.image_info_layout2.setSpacing(0)
        self.image_info_layout2.setContentsMargins(margin)

        self.image_widget2 = QWidget()
        self.image_layout2 = QHBoxLayout()
        self.image_label2 = ObjectViewer2D(self.image_widget2)
        self.image_label2.object_dialog = self
        self.slider = QLabeledSlider(Qt.Vertical)
        self.slider.setValue(0)
        self.range_slider = QLabeledRangeSlider(Qt.Vertical)
        self.range_slider.setValue((0,99))
        #self.mcube_widget.setMinimumHeight(200)
        #self.mcube_widget.setMinimumWidth(200)

        #self.slider.setTickInterval(1)
        #self.slider.setTickPosition(QSlider.TicksBothSides)
        self.slider.setSingleStep(1)
        self.range_slider.setSingleStep(1)
        #self.slider.setPageStep(1)
        #self.slider.setMinimum(0)
        #self.slider.setMaximum(0)
        self.slider.valueChanged.connect(self.sliderValueChanged)
        self.slider.sliderReleased.connect(self.sliderSliderReleased)
        self.range_slider.valueChanged.connect(self.rangeSliderValueChanged)
        self.range_slider.sliderReleased.connect(self.rangeSliderReleased)
        self.range_slider.setMinimumWidth(100)

        self.image_layout2.addWidget(self.image_label2,stretch=1)
        self.image_layout2.addWidget(self.slider)
        self.image_layout2.addWidget(self.range_slider)
        #self.image_layout2.addWidget(self.mcube_widget,stretch=1)
        self.image_widget2.setLayout(self.image_layout2)
        #self.image_layout2.setSpacing(20)
        #self.image_layout2.setSpacing(0)
        self.image_layout2.setContentsMargins(margin)

        #self.threed_widget = QWidget()
        #self.threed_layout = QHBoxLayout()
        self.slider2 = QLabeledSlider(Qt.Vertical)
        self.slider2.setValue(60)
        self.slider2.setMaximum(255)
        self.slider2.setSingleStep(1)
        self.slider2.valueChanged.connect(self.slider2ValueChanged)
        #self.slider2.editingFinished.connect(self.slider2EditingFinished)
        self.slider2.sliderReleased.connect(self.slider2SliderReleased)
        self.image_layout2.addWidget(self.slider2)
        #self.threed_layout.addWidget(self.mcube_widget,stretch=1)
        #self.threed_layout.addWidget(self.slider2)
        #self.threed_widget.setLayout(self.threed_layout)
        #self.threed_layout.setContentsMargins(QMargins(0,0,0,0))
        #self.image_widget2

        #self.image_layout2.addWidget(self.threed_widget,stretch=1)

        self.crop_layout2 = QHBoxLayout()
        self.crop_widget2 = QWidget()
        self.btnSetBottom = QPushButton(self.tr("Set Bottom"))
        self.btnSetBottom.clicked.connect(self.set_bottom)
        self.btnSetTop = QPushButton(self.tr("Set Top"))
        self.btnSetTop.clicked.connect(self.set_top)
        self.btnReset = QPushButton(self.tr("Reset"))
        self.btnReset.clicked.connect(self.reset_crop)
        self.btnUpdate3DView = QPushButton(self.tr("Update 3D View"))
        self.btnUpdate3DView.clicked.connect(self.update_3D_view)
        #self.cbxInverseImage = QCheckBox(self.tr("Inv."))
        #self.cbxInverseImage.setChecked(False)
        #self.cbxInverseImage.stateChanged.connect(self.cbxInverseImage_stateChanged)
        #self.inverse_image = False

        self.crop_layout2.addWidget(self.btnSetBottom,stretch=1)
        self.crop_layout2.addWidget(self.btnSetTop,stretch=1)
        self.crop_layout2.addWidget(self.btnReset,stretch=1)
        self.crop_layout2.addWidget(self.btnUpdate3DView,stretch=1)
        #self.crop_layout2.addWidget(self.cbxInverseImage,stretch=0)
        self.crop_widget2.setLayout(self.crop_layout2)
        #self.crop_layout2.setSpacing(0)
        self.crop_layout2.setContentsMargins(margin)

        self.status_layout = QHBoxLayout()
        self.status_widget = QWidget()
        self.edtStatus = QLineEdit()
        self.edtStatus.setReadOnly(True)
        self.edtStatus.setText("")
        self.status_layout.addWidget(self.edtStatus)
        self.status_widget.setLayout(self.status_layout)
        #self.status_layout.setSpacing(0)
        self.status_layout.setContentsMargins(margin)

        self.cbxOpenDirAfter = QCheckBox(self.tr("Open dir. after"))
        self.cbxOpenDirAfter.setChecked(True)
        self.btnSave = QPushButton(self.tr("Save cropped image stack"))
        self.btnSave.clicked.connect(self.save_result)
        self.btnExport = QPushButton(self.tr("Export 3D Model"))
        self.btnExport.clicked.connect(self.export_3d_model)

        self.btnPreferences = QPushButton(self.tr("Preferences"))
        self.btnPreferences.clicked.connect(self.show_preferences)
        self.button_layout = QHBoxLayout()
        self.button_layout.addWidget(self.cbxOpenDirAfter,stretch=0)
        self.button_layout.addWidget(self.btnSave,stretch=1)
        self.button_layout.addWidget(self.btnExport,stretch=1)
        self.button_layout.addWidget(self.btnPreferences,stretch=0)
        self.button_widget = QWidget()
        self.button_widget.setLayout(self.button_layout)
        #self.button_layout.setSpacing(0)
        self.button_layout.setContentsMargins(margin)



        self.right_layout = QVBoxLayout()
        self.right_widget = QWidget()
        #self.right_layout.setSpacing(0)
        self.right_layout.setContentsMargins(0,0,0,0)
        self.right_widget.setLayout(self.right_layout)
        #self.right_layout.addWidget(self.comboSize)
        self.right_layout.addWidget(self.dirname_widget)
        self.right_layout.addWidget(self.image_info_widget2)
        self.right_layout.addWidget(self.image_widget2)
        self.right_layout.addWidget(self.crop_widget2)
        self.right_layout.addWidget(self.button_widget)
        self.right_layout.addWidget(self.status_widget)
        #self.right_layout.addWidget(self.btnSave)

        self.main_layout = QHBoxLayout()
        self.main_widget = QWidget()
        self.main_widget.setLayout(self.main_layout)
        #self.main_layout.addWidget(self.left_widget)
        self.main_layout.addWidget(self.right_widget)
        #self.main_layout.setSpacing(0)
        #self.main_layout.setContentsMargins(11,,11,0)
        
        #self.main_layout.setContentsMargins(margin)
        self.status_text_format = self.tr("Crop indices: {}~{} Cropped image size: {}x{} ({},{})-({},{}) Estimated stack size: {} MB [{}]")
        self.progress_text_1_1 = self.tr("Saving image stack...")
        self.progress_text_1_2 = self.tr("Saving image stack... {}/{}")
        self.progress_text_2_1 = self.tr("Creating rescaled images level {}...")
        self.progress_text_2_2 = self.tr("Creating rescaled images level {}... {}/{}")
        self.progress_text_3_1 = self.tr("Checking rescaled images level {}...")
        self.progress_text_3_2 = self.tr("Checking rescaled images level {}... {}/{}")

        self.setCentralWidget(self.main_widget)

        self.mcube_widget = MCubeWidget(self.image_label2)
        self.mcube_widget.setGeometry(QRect(0,0,150,150))


        self.initialized = False

    def cbxInverseImage_stateChanged(self):
        #self.inverse_image = self.cbxInverseImage.isChecked()
        #self.image_label2.inverse_image = self.inverse_image
        pass

    def show_preferences(self):
        self.settings_dialog = PreferencesDialog(self)
        self.settings_dialog.setModal(True)
        self.settings_dialog.show()
        #self.settings_dialog.close()
        #self.settings_dialog = None

    def update_language(self):
        #print("main update language", self.m_app.language)
        translator = QTranslator()
        translator.load('CTHarvester_{}.qm'.format(self.m_app.language))
        self.m_app.installTranslator(translator)

        self.setWindowTitle("{} v{}".format(self.tr(PROGRAM_NAME), PROGRAM_VERSION))
        self.btnOpenDir.setText(self.tr("Open Directory"))
        self.edtDirname.setPlaceholderText(self.tr("Select directory to load CT data"))
        self.btnCreateThumbnail.setText(self.tr("Prepare View"))
        self.lblLevel.setText(self.tr("Level"))
        self.btnSetBottom.setText(self.tr("Set Bottom"))
        self.btnSetTop.setText(self.tr("Set Top"))
        self.btnReset.setText(self.tr("Reset"))
        self.cbxOpenDirAfter.setText(self.tr("Open dir. after"))
        self.btnSave.setText(self.tr("Save cropped image stack"))
        self.btnExport.setText(self.tr("Export 3D Model"))
        self.lblCount01.setText(self.tr("Count"))
        self.lblSize01.setText(self.tr("Size"))
        self.lblCount02.setText(self.tr("Count"))
        self.lblSize02.setText(self.tr("Size"))
        self.btnPreferences.setText(self.tr("Preferences"))
        self.status_text_format = self.tr("Crop indices: {}~{} Cropped image size: {}x{} ({},{})-({},{}) Estimated stack size: {} MB [{}]")
        self.progress_text_1_2 = self.tr("Saving image stack... {}/{}")
        self.progress_text_1_1 = self.tr("Saving image stack...")
        self.progress_text_2_1 = self.tr("Creating rescaled images level {}...")
        self.progress_text_2_2 = self.tr("Creating rescaled images level {}... {}/{}")
        self.progress_text_3_1 = self.tr("Checking rescaled images level {}...")
        self.progress_text_3_2 = self.tr("Checking rescaled images level {}... {}/{}")
        self.btnUpdate3DView.setText(self.tr("Update 3D View"))

    def set_bottom(self):
        #self.image_label2.set_bottom_idx(self.slider.value())
        #self.image_label2.set_curr_idx(self.slider.value())
        self.range_slider.setValue((self.slider.value(), self.range_slider.value()[1]))
        #self.update_3D_view()
        self.update_status()
    def set_top(self):
        #self.image_label2.set_top_idx(self.slider.value())
        #self.image_label2.set_curr_idx(self.slider.value())
        self.range_slider.setValue((self.range_slider.value()[0], self.slider.value()))
        #self.update_3D_view()
        self.update_status()

    def resizeEvent(self, a0: QResizeEvent) -> None:
        #print("resizeEvent")

        return super().resizeEvent(a0)

    def update_3D_view(self, update_model = True):
        #QApplication.setOverrideCursor(Qt.WaitCursor)#
        volume, roi_box = self.get_cropped_volume()
        bounding_box = self.minimum_volume.shape
        bounding_box = [ 0, bounding_box[0]-1, 0, bounding_box[1]-1, 0, bounding_box[2]-1 ]

        curr_slice_val = self.slider.value()/float(self.slider.maximum()) * self.minimum_volume.shape[0]
        self.mcube_widget.set_bounding_box(bounding_box)    
        self.mcube_widget.set_curr_slice(curr_slice_val)
        self.mcube_widget.set_roi_box(roi_box)
        if update_model:
            self.mcube_widget.set_volume(volume)
            self.mcube_widget.adjust_vertices()
            self.mcube_widget.oh_no()
        else:
            self.mcube_widget.adjust_vertices()
        #self.mcube_widget.set_volume(volume)
        #self.mcube_widget.adjust_vertices()
        #self.mcube_widget.oh_no() #generate_mesh()
        self.mcube_widget.repaint()
        #QApplication.restoreOverrideCursor()

    def update_curr_slice(self):
        return
        bounding_box = self.minimum_volume.shape
        bounding_box = [ 0, bounding_box[0]-1, 0, bounding_box[1]-1, 0, bounding_box[2]-1 ]
        curr_slice_val = self.slider.value()/float(self.slider.maximum()) * self.minimum_volume.shape[0]
        self.mcube_widget.set_curr_slice(curr_slice_val)
        self.mcube_widget.adjust_vertices()
        self.mcube_widget.repaint()

    def get_cropped_volume(self):
        # get current size idx
        size_idx = self.comboLevel.currentIndex()


        level_info = self.level_info[self.curr_level_idx]
        #print("level_info:", self.level_info)
        seq_begin = level_info['seq_begin']
        seq_end = level_info['seq_end']
        image_count = seq_end - seq_begin + 1

        # get current size
        curr_width = level_info['width']
        curr_height = level_info['height']

        # get top and bottom idx
        top_idx = self.image_label2.top_idx
        bottom_idx = self.image_label2.bottom_idx

        #get current crop box
        crop_box = self.image_label2.get_crop_area(imgxy=True)

        # get cropbox coordinates when image width and height is 1
        from_x = crop_box[0] / float(curr_width)
        from_y = crop_box[1] / float(curr_height)
        to_x = crop_box[2] / float(curr_width)
        to_y = crop_box[3] / float(curr_height)

        # get top idx and bottom idx when image count is 1
        top_idx = top_idx / float(image_count)
        bottom_idx = bottom_idx / float(image_count)

        # get cropped volume for smallest size
        smallest_level_info = self.level_info[-1]

        smallest_count = smallest_level_info['seq_end'] - smallest_level_info['seq_begin'] + 1
        bottom_idx = int(bottom_idx * smallest_count)
        top_idx = int(top_idx * smallest_count)
        from_x = int(from_x * smallest_level_info['width'])
        from_y = int(from_y * smallest_level_info['height'])
        to_x = int(to_x * smallest_level_info['width'])-1
        to_y = int(to_y * smallest_level_info['height'])-1

        volume = self.minimum_volume[bottom_idx:top_idx, from_y:to_y, from_x:to_x]
        return volume, [ bottom_idx, top_idx, from_y, to_y, from_x, to_x ]
        #self.mcube_widget.set_volume(volume)

    def export_3d_model(self):
        # open dir dialog for save

        threed_volume = []

        obj_filename, _ = QFileDialog.getSaveFileName(self, "Save File As", self.edtDirname.text(), "OBJ format (*.obj)")
        if obj_filename == "":
            return
        #print("obj_filename", obj_filename)

        threed_volume, _ = self.get_cropped_volume()
        isovalue = self.image_label2.isovalue
        vertices, triangles = mcubes.marching_cubes(threed_volume, isovalue)
        #print("threed_volume", threed_volume.shape, threed_volume.dtype)
        #print("vertices", vertices.shape, vertices.dtype)
        #print("triangles", triangles.shape, triangles.dtype)

        for i in range(len(vertices)):
            #continue
            # rotate 90 degrees around y axis
            vertices[i] = np.array([vertices[i][2],vertices[i][1],-1*vertices[i][0]])
            # rotate -90 degrees around x axis
            vertices[i] = np.array([vertices[i][0],-1*vertices[i][2],vertices[i][1]])


        # write as obj file format
        with open(obj_filename, 'w') as fh:
            for v in vertices:
                fh.write('v {} {} {}\n'.format(v[0], v[1], v[2]))
            #for vn in vertex_normals:
            #    fh.write('vn {} {} {}\n'.format(vn[0], vn[1], vn[2]))
            #for f in triangles:
            #    fh.write('f {}/{} {}/{} {}/{}\n'.format(f[0]+1, f[0]+1, f[1]+1, f[1]+1, f[2]+1, f[2]+1))
            for f in triangles:
                fh.write('f {} {} {}\n'.format(f[0]+1, f[1]+1, f[2]+1))

    def save_result(self):
        # open dir dialog for save
        target_dirname = QFileDialog.getExistingDirectory(self, self.tr('Select directory to save'), self.edtDirname.text())
        if target_dirname == "":
            return
        # get crop box info
        from_x = self.image_label2.crop_from_x
        from_y = self.image_label2.crop_from_y
        to_x = self.image_label2.crop_to_x
        to_y = self.image_label2.crop_to_y
        # get size idx
        size_idx = self.comboLevel.currentIndex()
        # get filename from level from idx
        top_idx = self.image_label2.top_idx
        bottom_idx = self.image_label2.bottom_idx

        current_count = 0
        total_count = top_idx - bottom_idx + 1
        self.progress_dialog = ProgressDialog(self)
        self.progress_dialog.update_language()
        self.progress_dialog.setModal(True)
        self.progress_dialog.show()
        self.progress_dialog.lbl_text.setText(self.progress_text_1_1)
        self.progress_dialog.pb_progress.setValue(0)
        QApplication.setOverrideCursor(Qt.WaitCursor)

        for i, idx in enumerate(range(bottom_idx, top_idx+1)):
            filename = self.settings_hash['prefix'] + str(self.level_info[size_idx]['seq_begin'] + idx).zfill(self.settings_hash['index_length']) + "." + self.settings_hash['file_type']
            # get full path
            if size_idx == 0:
                orig_dirname = self.edtDirname.text()
            else:
                orig_dirname = os.path.join(self.edtDirname.text(), ".thumbnail/" + str(size_idx))
            fullpath = os.path.join(orig_dirname, filename)
            # open image
            img = Image.open(fullpath)
            # crop image
            #print("crop", from_x, from_y, to_x, to_y)
            if from_x > -1:
                img = img.crop((from_x, from_y, to_x, to_y))
            # save image
            img.save(os.path.join(target_dirname, filename))

            self.progress_dialog.lbl_text.setText(self.progress_text_1_2.format(i+1, int(total_count)))
            self.progress_dialog.pb_progress.setValue(int(((i+1)/float(int(total_count)))*100))
            self.progress_dialog.update()
            QApplication.processEvents()

        QApplication.restoreOverrideCursor()
        self.progress_dialog.close()
        self.progress_dialog = None
        if self.cbxOpenDirAfter.isChecked():
            os.startfile(target_dirname)


    def rangeSliderValueChanged(self):
        (bottom_idx, top_idx) = self.range_slider.value()
        self.image_label2.set_bottom_idx(bottom_idx)
        self.image_label2.set_top_idx(top_idx)
        self.image_label2.calculate_resize()
        self.image_label2.repaint()
        self.update_3D_view()
        self.update_status()

    def rangeSliderReleased(self):
        print("range slider released")
        self.update_3D_view()
        #self.image_label2.calculate_resize()
        return

    def sliderValueChanged(self):
        # print current slide value
        #print("sliderValueChanged")
        #print("slider value:", self.slider.value())
        # get scale factor
        if not self.initialized:
            return
        size_idx = self.comboLevel.currentIndex()
        curr_image_idx = self.slider.value()
        #print("curr_image_idx:", curr_image_idx)
        #print("size_idx:", size_idx)
        #print("settings hash", self.settings_hash)
        if size_idx < 0:
            size_idx = 0
        # get directory for size idx
        if size_idx == 0:
            dirname = self.edtDirname.text()
            #filename = self.lstFileList.item(self.slider.value()).text()
            filename = self.settings_hash['prefix'] + str(self.level_info[size_idx]['seq_begin'] + self.slider.value()).zfill(self.settings_hash['index_length']) + "." + self.settings_hash['file_type']
        else:
            dirname = os.path.join(self.edtDirname.text(), ".thumbnail/" + str(size_idx))
            # get filename from level from idx
            filename = self.settings_hash['prefix'] + str(self.level_info[size_idx]['seq_begin'] + self.slider.value()).zfill(self.settings_hash['index_length']) + "." + self.settings_hash['file_type']
        #print("dirname:", dirname)
        #print("filename:", filename)

        self.image_label2.set_image(os.path.join(dirname, filename))
        self.image_label2.set_curr_idx(self.slider.value())
        self.update_curr_slice()
        self.update_3D_view(update_model=False)
        #self.edtCurrentImage.setText(str(self.slider.value()))
        #self.image_label2.setPixmap(QPixmap(os.path.join(dirname, filename)).scaledToWidth(512))

    def reset_crop(self):
        #self.image_label2.set_top_idx(self.slider.minimum())
        #self.image_label2.set_bottom_idx(self.slider.maximum())
        self.image_label2.set_curr_idx(self.slider.value())
        self.image_label2.reset_crop()
        self.range_slider.setValue((self.slider.minimum(), self.slider.maximum()))
        self.canvas_box = None
        #self.update_3d_view(update_model=False)
        self.update_status()

    def update_status(self):
        ( bottom_idx, top_idx ) = self.range_slider.value()
        [ x1, y1, x2, y2 ] = self.image_label2.get_crop_area(imgxy=True)
        count = ( top_idx - bottom_idx + 1 )
        #self.status_format = self.tr("Crop indices: {}~{}    Cropped image size: {}x{}    Estimated stack size: {} MB [{}]")
        status_text = self.status_text_format.format(bottom_idx, top_idx, x2 - x1, y2 - y1, x1, y1, x2, y2, round(count * (x2 - x1 ) * (y2 - y1 ) / 1024 / 1024 , 2), str(self.image_label2.edit_mode))
        self.edtStatus.setText(status_text)

    def initializeComboSize(self):
        #print("initializeComboSize")
        self.comboLevel.clear()
        for level in self.level_info:
            self.comboLevel.addItem( level['name'])

    def comboLevelIndexChanged(self):
        #print("-----------------------------[[[comboSizeIndexChanged]]]-----------------------------")
        self.prev_level_idx = self.curr_level_idx
        self.curr_level_idx = self.comboLevel.currentIndex()
        if self.curr_level_idx < 0:
            return
        
        #print("prev_level_idx:", self.prev_level_idx)
        #print("curr_level_idx:", self.curr_level_idx)
        level_info = self.level_info[self.curr_level_idx]
        #print("level_info:", self.level_info)
        seq_begin = level_info['seq_begin']
        seq_end = level_info['seq_end']

        self.edtImageDimension2.setText(str(level_info['width']) + " x " + str(level_info['height']))
        image_count = seq_end - seq_begin + 1
        self.edtNumImages2.setText(str(image_count))

        if not self.initialized:
            #print("not initialized. image_count:", image_count)
            self.slider.setMaximum(image_count - 1)
            self.slider.setMinimum(0)
            self.slider.setValue(0)
            self.range_slider.setRange(0,image_count - 1)
            self.range_slider.setValue((0, image_count - 1))
            #print("range_slider value:", self.range_slider.value())
            #print("range_slider range:", self.range_slider.minimum(), self.range_slider.maximum())
            self.curr_level_idx = 0
            self.prev_level_idx = 0
            self.initialized = True


        level_diff = self.prev_level_idx-self.curr_level_idx
        #print("level_diff:", level_diff)
        #print("prev_level_idx:", self.prev_level_idx)
        #print("curr_level_idx:", self.curr_level_idx)
        curr_idx = self.slider.value()
        #print("curr_idx 1:", curr_idx)
        curr_idx = int(curr_idx * (2**level_diff))
        #print("curr_idx 2:", curr_idx)

        (bottom_idx, top_idx) = self.range_slider.value()
        #print("bottom_idx:", bottom_idx)
        #print("top_idx:", top_idx)
        bottom_idx = int(bottom_idx * (2**level_diff))
        top_idx = int(top_idx * (2**level_diff))
        #print("bottom_idx:", bottom_idx)
        #print("top_idx:", top_idx)

        self.range_slider.setRange(0, image_count - 1)
        self.range_slider.setValue((bottom_idx, top_idx))

        self.slider.setMaximum(image_count -1)
        self.slider.setMinimum(0)
        #print("curr_idx 3:", curr_idx)
        self.slider.setValue(curr_idx)
        #print("curr_idx 4:", self.slider.value())

        self.sliderValueChanged()
        self.update_status()

    def create_thumbnail(self):
        # determine thumbnail size
        #print("create thumbnail")
        MAX_THUMBNAIL_SIZE = 512
        size =  max(int(self.settings_hash['image_width']), int(self.settings_hash['image_height']))
        width = int(self.settings_hash['image_width'])
        height = int(self.settings_hash['image_height'])

        i = 0
        # create temporary directory for thumbnail
        dirname = self.edtDirname.text()

        self.minimum_volume = []
        seq_begin = self.settings_hash['seq_begin']
        seq_end = self.settings_hash['seq_end']

        current_count = 0
        self.progress_dialog = ProgressDialog(self)
        self.progress_dialog.update_language()
        self.progress_dialog.setModal(True)
        self.progress_dialog.show()
        QApplication.setOverrideCursor(Qt.WaitCursor)

        while True:
            size /= 2
            width = int(width / 2)
            height = int(height / 2)

            if i == 0:
                from_dir = dirname
            else:
                from_dir = os.path.join(self.edtDirname.text(), ".thumbnail/" + str(i))

            total_count = seq_end - seq_begin + 1
            self.progress_dialog.lbl_text.setText(self.progress_text_2_1.format(i+1))
            self.progress_dialog.pb_progress.setValue(0)

            # create thumbnail
            to_dir = os.path.join(self.edtDirname.text(), ".thumbnail/" + str(i+1))
            if not os.path.exists(to_dir):
                os.makedirs(to_dir)
            last_count = 0

            for idx, seq in enumerate(range(seq_begin, seq_end+1, 2)):
                filename1 = self.settings_hash['prefix'] + str(seq).zfill(self.settings_hash['index_length']) + "." + self.settings_hash['file_type']
                filename2 = self.settings_hash['prefix'] + str(seq+1).zfill(self.settings_hash['index_length']) + "." + self.settings_hash['file_type']
                filename3 = os.path.join(to_dir, self.settings_hash['prefix'] + str(seq_begin + idx).zfill(self.settings_hash['index_length']) + "." + self.settings_hash['file_type'])

                if os.path.exists(filename3):  
                    self.progress_dialog.lbl_text.setText(self.progress_text_3_2.format(i+1, idx+1, int(total_count/2)))
                    self.progress_dialog.pb_progress.setValue(int(((idx+1)/float(int(total_count/2)))*100))
                    self.progress_dialog.update()
                    QApplication.processEvents()
                    if size < MAX_THUMBNAIL_SIZE:
                        img= Image.open(os.path.join(from_dir,filename3))
                        #print("new_img_ops:", np.array(img).shape)
                        self.minimum_volume.append(np.array(img))
                    continue
                else:
                    self.progress_dialog.lbl_text.setText(self.progress_text_2_2.format(i+1, idx+1, int(total_count/2)))
                    self.progress_dialog.pb_progress.setValue(int(((idx+1)/float(int(total_count/2)))*100))
                    self.progress_dialog.update()
                    QApplication.processEvents()
                    # check if filename exist
                    img1 = None
                    if os.path.exists(os.path.join(from_dir, filename1)):
                        img1 = Image.open(os.path.join(from_dir, filename1))
                        if img1.mode[0] == 'I':
                            img1 = Image.fromarray(np.divide(np.array(img1), 2**8-1)).convert('L')
                    img2 = None
                    if os.path.exists(os.path.join(from_dir, filename2)):
                        img2 = Image.open(os.path.join(from_dir, filename2))
                        if img2.mode[0] == 'I':
                            img2 = Image.fromarray(np.divide(np.array(img2), 2**8-1)).convert('L')
                    # average two images
                    #print("img1:", img1.mode, "img2:", img2.mode)
                    if img1 is None or img2 is None:
                        last_count = -1
                        continue
                    new_img_ops = ImageChops.add(img1, img2, scale=2.0)
                    # resize to half
                    new_img_ops = new_img_ops.resize((int(img1.width / 2), int(img1.height / 2)))
                    # save to temporary directory
                    new_img_ops.save(filename3)

                    if size < MAX_THUMBNAIL_SIZE:
                        #print("new_img_ops:", np.array(new_img_ops).shape)
                        self.minimum_volume.append(np.array(new_img_ops))

            i+= 1
            seq_end = int((seq_end - seq_begin) / 2) + seq_begin + last_count
            self.level_info.append( {'name': "Level " + str(i), 'width': width, 'height': height, 'seq_begin': seq_begin, 'seq_end': seq_end} )
            if size < MAX_THUMBNAIL_SIZE:
                self.minimum_volume = np.array(self.minimum_volume)
                #print("minimum_volume:", self.minimum_volume.shape)
                bounding_box = self.minimum_volume.shape
                bounding_box = np.array([ 0, bounding_box[0]-1, 0, bounding_box[1]-1, 0, bounding_box[2]-1 ])

                curr_slice_val = self.slider.value()/float(self.slider.maximum()) * self.minimum_volume.shape[0]
                self.mcube_widget.set_bounding_box(bounding_box)
                self.mcube_widget.set_curr_slice(curr_slice_val)
                self.mcube_widget.set_roi_box(bounding_box)
                self.mcube_widget.set_volume(self.minimum_volume)
                self.mcube_widget.adjust_vertices()
                self.mcube_widget.generate_mesh()
                self.mcube_widget.repaint()


                self.mcube_widget.generate_mesh()
                break
            
        QApplication.restoreOverrideCursor()
        self.progress_dialog.close()
        self.progress_dialog = None
        self.initializeComboSize()
        self.reset_crop()

    def slider2ValueChanged(self, value):
        #print("value:", value)
        self.image_label2.set_isovalue(value)
        self.mcube_widget.set_isovalue(value)
        self.image_label2.calculate_resize()
        #self.update_3D_view()

    def sliderSliderReleased(self):
        self.update_3D_view(False)
    
    def slider2SliderReleased(self):
        print("slider2SliderReleased")
        self.update_3D_view()
        #self.threed
        #print("released")
        return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self.mcube_widget.generate_mesh()
        self.mcube_widget.repaint()
        QApplication.restoreOverrideCursor()


    def lstFileListSelectionChanged(self):
        #print("lstFileListSelectionChanged")
        self.image_label.setPixmap(QPixmap(os.path.join(self.edtDirname.text(), self.lstFileList.currentItem().text())).scaledToWidth(512))

    def sort_file_list_from_dir(self, directory_path):
        # Step 1: Get a list of all files in the directory
        #directory_path = "/path/to/your/directory"  # Replace with the path to your directory
        all_files = [f for f in os.listdir(directory_path) if os.path.isfile(os.path.join(directory_path, f))]

        # Step 2: Regular expression pattern
        pattern = r'^(.*?)(\d+)\.(\w+)$'

        ct_stack_files = []
        matching_files = []
        other_files = []
        prefix_hash = {}
        extension_hash = {}
        settings_hash = {}

        for file in all_files:
            if re.match(pattern, file):
                matching_files.append(file)
                if re.match(pattern, file).group(1) in prefix_hash:
                    prefix_hash[re.match(pattern, file).group(1)] += 1
                else:
                    prefix_hash[re.match(pattern, file).group(1)] = 1
                if re.match(pattern, file).group(3) in extension_hash:
                    extension_hash[re.match(pattern, file).group(3)] += 1
                else:
                    extension_hash[re.match(pattern, file).group(3)] = 1

            else:
                other_files.append(file)

        # determine prefix
        max_prefix_count = 0
        for prefix in prefix_hash:
            if prefix_hash[prefix] > max_prefix_count:
                max_prefix_count = prefix_hash[prefix]
                max_prefix = prefix
        #print("max_prefix:", max_prefix)
        #print("max_count:", max_prefix_count)

        # determine extension
        max_extension_count = 0
        for extension in extension_hash:
            if extension_hash[extension] > max_extension_count:
                max_extension_count = extension_hash[extension]
                max_extension = extension
        #print("max_extension:", max_extension)
        #print("max_count:", max_extension_count)

        if matching_files:
            for file in matching_files:
                if re.match(pattern, file).group(1) == max_prefix and re.match(pattern, file).group(3) == max_extension:
                    ct_stack_files.append(file)


        # Determine the pattern if needed further
        if ct_stack_files:
            # If there are CT stack files, we can determine some common patterns
            # Here as an example, we are just displaying the prefix of the first matched file
            # This can be expanded upon based on specific needs
            first_file = ct_stack_files[0]
            last_file = ct_stack_files[-1]
            imagefile_name = os.path.join(directory_path, first_file)
            # get width and height
            img = Image.open(imagefile_name)
            width, height = img.size


            match1 = re.match(pattern, first_file)
            match2 = re.match(pattern, last_file)
            #if match1:
                #print("\nDetermined Pattern:")
                #print("Prefix:", match1.group(1))
                #print("Extension:", match1.group(3))

            if match1 and match2:
                #print("Start Index:", match1.group(2))
                #print("End Index:", match2.group(2))
                start_index = match1.group(2)
                end_index = match2.group(2)
            image_count = int(match2.group(2)) - int(match1.group(2)) + 1
            number_of_images = len(ct_stack_files)
            #print("Number of images:", number_of_images)
            #print("Image count:", image_count)
            seq_length = len(match1.group(2))
            #print("Sequence length:", seq_length)

            settings_hash['prefix'] = prefix
            settings_hash['image_width'] = width
            settings_hash['image_height'] = height
            settings_hash['file_type'] = max_extension
            settings_hash['index_length'] = seq_length
            settings_hash['seq_begin'] = start_index
            settings_hash['seq_end'] = end_index
            #print("Settings hash:", settings_hash)
            settings_hash['index_length'] = int(settings_hash['index_length'])
            settings_hash['seq_begin'] = int(settings_hash['seq_begin'])
            settings_hash['seq_end'] = int(settings_hash['seq_end'])

            return settings_hash
        else:
            return None
        


    def open_dir(self):
        #pass
        #print("open_dir")
        ddir = QFileDialog.getExistingDirectory(self, self.tr("Select directory"), self.m_app.default_directory)
        if ddir:
        # ddir is a QString containing the path to the directory you selected
            #print("loading from:", ddir)  # this will output something like 'C://path/you/selected'
            self.edtDirname.setText(ddir)
            self.m_app.default_directory = os.path.dirname(ddir)
            #print("default directory:", self.m_app.default_directory)
        else:
            return
        self.settings_hash = {}
        self.initialized = False
        image_file_list = []
        self.lstFileList.clear()
        QApplication.setOverrideCursor(Qt.WaitCursor)

        files = [f for f in os.listdir(ddir) if os.path.isfile(os.path.join(ddir, f))]

        for file in files:
            # get extension
            ext = os.path.splitext(file)[-1].lower()
            if ext in [".bmp", ".jpg", ".png", ".tif", ".tiff"]:
                pass #image_file_list.append(file)
            elif ext == '.log':
                #fn = file
                #print("log file:", ddir, file)
                settings = QSettings(os.path.join(ddir, file), QSettings.IniFormat)
                #print("settings:", settings, settings.fileName(), settings.status(), settings.allKeys())
                prefix = settings.value("File name convention/Filename Prefix")
                if not prefix:
                    continue
                if file != prefix + ".log":
                    continue

                self.settings_hash['prefix'] = settings.value("File name convention/Filename Prefix")
                self.settings_hash['image_width'] = settings.value("Reconstruction/Result Image Width (pixels)")
                self.settings_hash['image_height'] = settings.value("Reconstruction/Result Image Height (pixels)")
                self.settings_hash['file_type'] = settings.value("Reconstruction/Result File Type")
                self.settings_hash['index_length'] = settings.value("File name convention/Filename Index Length")
                self.settings_hash['seq_begin'] = settings.value("Reconstruction/First Section")
                self.settings_hash['seq_end'] = settings.value("Reconstruction/Last Section")
                #print("Settings hash:", self.settings_hash)
                #print("prefix:", prefix)
                self.settings_hash['index_length'] = int(self.settings_hash['index_length'])
                self.settings_hash['seq_begin'] = int(self.settings_hash['seq_begin'])
                self.settings_hash['seq_end'] = int(self.settings_hash['seq_end'])
                #print("Settings hash:", self.settings_hash)
                self.edtNumImages.setText(str(self.settings_hash['seq_end'] - self.settings_hash['seq_begin'] + 1))
                self.edtImageDimension.setText(str(self.settings_hash['image_width']) + " x " + str(self.settings_hash['image_height']))
                #print("Settings hash:", settings_hash)
        #print("Settings hash:", self.settings_hash)
        if 'prefix' not in self.settings_hash:
            #print("prefix not found. trying to find prefix from file name")
            self.settings_hash = self.sort_file_list_from_dir(ddir)
            if self.settings_hash is None:
                return
            #return
        #print("Settings hash:", self.settings_hash)
        #print("dir:", ddir)
        for seq in range(self.settings_hash['seq_begin'], self.settings_hash['seq_end']+1):
            filename = self.settings_hash['prefix'] + str(seq).zfill(self.settings_hash['index_length']) + "." + self.settings_hash['file_type']
            self.lstFileList.addItem(filename)
            image_file_list.append(filename)
        self.original_from_idx = 0
        self.edtFromImage.setText(image_file_list[0])
        self.original_to_idx = len(image_file_list) - 1
        self.edtToImage.setText(image_file_list[-1])
        self.image_label.setPixmap(QPixmap(os.path.join(ddir,image_file_list[0])).scaledToWidth(512))
        self.image_label2.setPixmap(QPixmap(os.path.join(ddir,image_file_list[0])).scaledToWidth(512))
        self.level_info = []
        self.level_info.append( {'name': 'Original', 'width': self.settings_hash['image_width'], 'height': self.settings_hash['image_height'], 'seq_begin': self.settings_hash['seq_begin'], 'seq_end': self.settings_hash['seq_end']} )
        #print("level_info in open_dir:", self.level_info)
        #self.initializeComboSize()
        #self.open_dir()
        QApplication.restoreOverrideCursor()
        self.create_thumbnail()

    def read_settings(self):
        settings = self.m_app.settings

        self.m_app.remember_directory = value_to_bool(settings.value("Remember directory", True))
        #print("read settings remember directory:", self.m_app.remember_directory)
        if self.m_app.remember_directory:
            self.m_app.default_directory = settings.value("Default directory", ".")
        else:
            self.m_app.default_directory = "."
        #print("read settings default directory:", self.m_app.default_directory)

        self.m_app.remember_geometry = value_to_bool(settings.value("Remember geometry", True))
        if self.m_app.remember_geometry:
            self.setGeometry(settings.value("MainWindow geometry", QRect(100, 100, 600, 550)))
        else:
            self.setGeometry(QRect(100, 100, 600, 550))
        self.m_app.language = settings.value("Language", "en")

    def save_settings(self):
        #print("save default directory:", self.m_app.default_directory)
        if self.m_app.remember_directory:
            self.m_app.settings.setValue("Default directory", self.m_app.default_directory)
            #print("save default directory:", self.m_app.default_directory)
        if self.m_app.remember_geometry:
            self.m_app.settings.setValue("MainWindow geometry", self.geometry())

    def closeEvent(self, event):
        self.save_settings()
        event.accept()
        

if __name__ == "__main__":
    app = QApplication(sys.argv)

    app.setWindowIcon(QIcon(resource_path('CTHarvester_48_2.png')))
    app.settings = QSettings(QSettings.IniFormat, QSettings.UserScope,COMPANY_NAME, PROGRAM_NAME)

    translator = QTranslator(app)
    app.language = app.settings.value("Language", "en")
    translator.load(resource_path("CTHarvester_{}.qm".format(app.language)))
    app.installTranslator(translator)


    #app.settings = 
    #app.preferences = QSettings("Modan", "Modan2")

    #WindowClass의 인스턴스 생성
    myWindow = CTHarvesterMainWindow()

    #프로그램 화면을 보여주는 코드
    myWindow.show()

    #프로그램을 이벤트루프로 진입시키는(프로그램을 작동시키는) 코드
    app.exec_()
'''
pyinstaller --onefile --noconsole --add-data "*.png;." --add-data "*.qm;." --icon="CTHarvester_48_2.png" CTHarvester.py

pylupdate5 CTHarvester.py -ts CTHarvester_en.ts
pylupdate5 CTHarvester.py -ts CTHarvester_ko.ts
linguist

'''