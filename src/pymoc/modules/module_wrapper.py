import numpy as np
from pymoc.modules import Column, Equi_Column, Psi_SO, SO_ML
from pymoc.utils import has_method


class ModuleWrapper(object):
  r"""
  Module Wrapper

  Instances of this class wrap individual phsyical modules 
  (e.g. advective-diffusive columns, thermal wind streamfunctions)
  for use in the model driver. The module wrapper is responsible for 
  timestepping & updating modules, & communication between neighboring
  modules.
  
  By convention geographic north & east are defined as 
  being to the "right" or "rightward", while geographic south & west 
  are defined as being the the "left" or "leftward". Modules are categorized
  as "basins" with time evolving density profiles (e.g. columns, mixed layers),
  or "couplers" with streamfunctions that maintain the dynamical balance between
  neighboring basins (e.g. thermal wind streamfunction, SO transport).
  """
  def __init__(
      self,
      module=None,
      name=None,
      left_neighbors=None,
      right_neighbors=None,
  ):
    r"""
    Parameters
    ----------

    module : module class instance
             Physics module being wrapped
    name : string
           Name of the module being wrapped (e.g. Atlantic Basin, AMOC)
    left_neighbors : list; optional
                     List of modules to the "left" of the module being wrapped.
                     Couplers may have at most one left neighbor.
    right_neighbors : list; optional
                      List of modules to the "right" of the module being wrapped.
                      Couplers may have at most one right neighbor.
    """
    self.module = module
    self.name = name
    self.left_neighbors = []
    self.right_neighbors = []

    self.key = name.replace(' ', '_').lower().strip('_')
    self.psi = [0, 0]

    if left_neighbors or right_neighbors:
      self.add_neighbors(
          left_neighbors=left_neighbors, right_neighbors=right_neighbors
      )

  @property
  def module_type(self):
    r"""
    Return whether the wrapped module is a basin or coupler.

    Returns
    -------

    module_type : string
        The type of the wrapped module.
    """
    return self.module.module_type

  def timestep_basin(self, dt=None):
    r"""
    Invoke the timestep method of the wrapped basin module.

    Parameters
    ----------

    dt : int
         Numerical timestep over which solution are iterated. Units: s

    """
    if self.module_type != 'basin':
      raise TypeError('Cannot use timestep_basin on non-basin modules.')

    module = self.module
    wA = 0.0
    for neighbor in self.right_neighbors:
      wA += neighbor.psi[0] * 1e6
    for neighbor in self.left_neighbors:
      wA -= neighbor.psi[-1] * 1e6
    if isinstance(module, SO_ML):
      neighbor_b = [n.right_neighbors[0].b for n in self.right_neighbors]
      b_min = np.min(neighbor_b)
      b_max = np.max(neighbor_b)
      db = np.max([np.min(np.diff(np.sort(np.unique(np.asarray(neighbor_b))))), 1e-6])
      b_basin = np.arange(b_max, b_min, -db)
      Psi_b = np.sum([np.interp(b_basin[::-1], n.right_neighbors[0].b[::-1], n.psi[0][::-1])[::-1] for n in self.right_neighbors], axis=0)
    
      # b_basin = self.right_neighbors[0].right_neighbors[0].b
      # construct "universal" bouyancy grid
      # add streamfunctions
      # pass summed psi and univerral b_basin
      module.timestep(Psi_b=Psi_b, dt=dt, b_basin=b_basin)
    else:
      module.timestep(wA=wA, dt=dt)

  def update_coupler(self):
    r"""
    Invoke the update method of the wrapped coupler.

    """
    if self.module_type != 'coupler':
      raise TypeError('Cannot use update_coupler on non-coupler modules.')

    module = self.module
    get_b = lambda neighbors: neighbors[0].b if len(neighbors) > 0 else None
    b1 = get_b(self.left_neighbors)
    b2 = get_b(self.right_neighbors)

    if hasattr(module, 'bs'):
      module.update(b=b2, bs=b1)
    else:
      module.update(b1=b1, b2=b2)

    module.solve()
    self.psi = module.Psibz() if has_method(self.module, 'Psibz') else [module.Psi]

  @property
  def b(self):
    r"""
    Return the buoyancy profile of the wrapped module. This is the
    vertical buoyancy profile for columns, and the surface buoyancy
    for channels and couplers

    Returns
    -------

    module_type : func or ndarray
                  The buoyancy profile of the wrapped module, with type consistent
                  with the module.
    """

    if self.module_type != 'basin':
      return None
    elif hasattr(self.module, 'b'):
      return self.module.b
    elif hasattr(self.module, 'bs'):
      return self.module.bs
    return None

  @property
  def neighbors(self):
    r"""
    Return a list of all of the module's neighbors.

    Returns
    -------

    neighbors : ndarray
                Array pointing to the wrappers for each
                neighboring module.
    
    """
    return self.left_neighbors + self.right_neighbors

  def add_left_neighbor(self, new_neighbor, is_backlinking=False):
    r"""
    Add a neighbor to the "left" of the current module. This method validates
    that the neighbor is unique, can occupy the left neighbor position, and
    optionally backlinks to the current module (i.e. sets the current module 
    as the new neighbor's right neighbor).


    Parameters
    ----------

    new_neighbor: module_wrapper
                  A wrapper pointing to the module being added as a lefthand neighbor.
    is_backlinking: boolean; optional
                 Whether this neighbor is being added as part of the backlinking process. Prevents circular backlinking.
                 
    """
    self.validate_neighbor_uniqueness(new_neighbor)
    self.validate_coupler_neighbor_direction('left')
    self.left_neighbors.append(new_neighbor)
    if not is_backlinking:
      self.backlink_neighbor(new_neighbor)

  def add_right_neighbor(self, new_neighbor, is_backlinking=False):
    r"""
    Add a neighbor to the "right" of the current module. This method validates
    that the neighbor is unique, can occupy the right neighbor position, and
    optionally backlinks to the current module (i.e. sets the current module 
    as the new neighbor's left neighbor).


    Parameters
    ----------

    new_neighbor: module_wrapper
                  A wrapper pointing to the module being added as a righthand neighbor.
    is_backlinking: boolean; optional
                 Whether this neighbor is being added as part of the backlinking process. Prevents circular backlinking.
                 
    """
    self.validate_neighbor_uniqueness(new_neighbor)
    self.validate_coupler_neighbor_direction('right')
    self.right_neighbors.append(new_neighbor)
    if not is_backlinking:
      self.backlink_neighbor(new_neighbor)

  def add_neighbors(self, left_neighbors=None, right_neighbors=None):
    r"""
    Add multiple neighbors to the current module.

    Parameters
    ----------

    left_neighbors: ndarray; optional
                    A list of modules to be added to the left of the current module
    right_neighbors: ndarray; optional
                     A list of modules to be added to the right of the current module

    """
    if left_neighbors is not None and len(left_neighbors) > 0:
      for neighbor in left_neighbors:
        self.add_left_neighbor(neighbor)

    if right_neighbors is not None and len(right_neighbors) > 0:
      for neighbor in right_neighbors:
        self.add_right_neighbor(neighbor)

  def validate_neighbor_uniqueness(self, neighbor):
    r"""
    Validate that the current module does not already have the specified module as a neighbor.
    If already a neighbor, raises a KeyError exception.

    Parameters
    ----------

    neighbor: module_wrapper
              The module being checked against for uniqueness

    """
    if neighbor in self.neighbors:
      raise KeyError(
          'Cannot add module ' + neighbor.name + ' as a neighbor of ' +
          self.name + ' because they are already coupled.'
      )

  def validate_coupler_neighbor_direction(self, direction):
    r"""
    Validate that the current module does not already have a neighbor in the specified direction
    if a coupler. If the current module is a coupler, and direction is occupied, raises a ValueError exception.

    Parameters
    ----------

    direction: string
               The direction being checked against for availability

    """
    if self.module_type == 'coupler':
      # We don't need to explicitly check that a coupler has two or fewer neighbors, as the enforcement of only one left, only one right, and only being able to point left or right implicitly enforces that condition.
      if len(self.left_neighbors) > 0 and direction == 'left' or len(
          self.right_neighbors
      ) > 0 and direction == 'right':
        raise ValueError(
            'Cannot have a coupler linked in the same direction more than once. Please check your configuration.'
        )

  def backlink_neighbor(self, neighbor):
    r"""
    Point the specified neighbor back at the current module. If a right neighbor, the current module becomes
    its left neighbor. Otherwise, the current module becomes its right neighbor.

    Parameters
    ----------

    neighbor: module_wrapper
              Wrapper pointing to the module being backlinked from

    """
    if neighbor in self.right_neighbors:
      neighbor.add_left_neighbor(self, is_backlinking=True)
    else:
      neighbor.add_right_neighbor(self, is_backlinking=True)
