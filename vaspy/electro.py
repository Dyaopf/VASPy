# -*- coding:utf-8 -*-
"""
========================================================================
Provide electro-related file class which do operations on these files.
========================================================================
Written by PytLab <shaozhengjiang@gmail.com>, September 2015
Updated by PytLab <shaozhengjiang@gmail.com>, May 2016
========================================================================

"""
import copy
import logging
from string import whitespace

import numpy as np
from scipy.integrate import simps
from scipy.interpolate import interp2d
import mpl_toolkits.mplot3d
import matplotlib.pyplot as plt
#whether mayavi installed
try:
    from mayavi import mlab
    mayavi_installed = True
except ImportError:
    mayavi_installed = False

from plotter import DataPlotter
from atomco import PosCar
from functions import line2list


class DosX(DataPlotter):
    def __init__(self, filename, field=' ', dtype=float):
        """
        Create a DOS file class.

        Example:

        >>> a = DosX(filename='DOS1')

        Class attributes descriptions
        =======================================================
          Attribute      Description
          ============  =======================================
          filename       string, name of the SPLITED DOS file
          field          string, separator of a line
          dtype          type, convertion type of data

          reset_data     method, reset object data
          plotsum        method, 绘制多列加合的图像
          ============  =======================================
        """
        DataPlotter.__init__(self, filename=filename, field=' ', dtype=float)

    def __add__(self, dosx_inst):
        sum_dosx = copy.deepcopy(self)
        #相加之前判断能量分布是否相同
        same = (self.data[:, 0] == dosx_inst.data[:, 0]).all()
        if not same:
            raise ValueError('Energy is different.')
        sum_dosx.data[:, 1:] = self.data[:, 1:] + dosx_inst.data[:, 1:]
        sum_dosx.filename = 'DOS_SUM'

        return sum_dosx

    def reset_data(self):
        "Reset data array to zeros."
        self.data[:, 1:] = 0.0

    def plotsum(self, xcol, ycols, fill=True,
                show_dbc=True, show_fermi=True):
        '''
        绘制多列加合的图像.

        Parameter
        ---------
        xcol: int
            column number of data for x values
        ycols: tuple of int
            column numbers of data for y values
            (start, stop[, step])
        Example:
        >>> a.plotsum(0, (1, 3))
        >>> a.plotsum(0, (5, 10, 2))
        '''
        x = self.data[:, xcol]
        if len(ycols) == 2:
            start, stop = ycols
            step = 1
        else:
            start, stop, step = ycols
        ys = self.data[:, start:stop:step]
        y = np.sum(ys, axis=1)
        ymax = np.max(y)
        #plot
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.plot(x, y, linewidth=5, color='#104E8B')
        #plot fermi energy auxiliary line
        if show_fermi:
            #Fermi verical line
            xfermi = np.array([0.0]*50)
            yfermi = np.linspace(0, int(ymax+1), 50)
            ax.plot(xfermi, yfermi, linestyle='dashed',
                    color='#4A708B', linewidth=3)
        # fill area from minus infinit to 0
        if fill:
            minus_x = np.array([i for i in x if i <= 0])
            minus_y = y[: len(minus_x)]
            ax.fill_between(minus_x, minus_y, facecolor='#B9D3EE',
                            interpolate=True)
        # show d band center line
        if show_dbc:
            dbc = self.get_dband_center()
            x_dbc = np.array([dbc]*50)
            y_dbc = np.linspace(0, int(ymax+1), 50)
            ax.plot(x_dbc, y_dbc, linestyle='dashed',
                    color='#C67171', linewidth=3)

        ax.set_xlabel(r'$\bf{E - E_F(eV)}$', fontdict={'fontsize': 20})
        ax.set_ylabel(r'$\bf{pDOS(arb. unit)}$', fontdict={'fontsize': 20})
        fig.show()

        return

    def tofile(self):
        "生成文件"
        "DosX object to DOS file."
        ndata = self.data.shape[1]  # data number in a line
        data = self.data.tolist()
        content = ''
        for datalist in data:
            content += ('%12.8f'*ndata + '\n') % tuple(datalist)
        with open(self.filename(), 'w') as f:
            f.write(content)

        return

    def get_dband_center(self):
        "Get d-band center of the DosX object."
        #合并d轨道DOS
        if self.data.shape[1] == 10:
            yd = np.sum(self.data[:, 5:10], axis=1)
        #获取feimi能级索引
        for idx, E in enumerate(self.data[:, 0]):
            if E >= 0:
                nfermi = idx
                break
        E = self.data[: nfermi+1, 0]  # negative inf to Fermi
        dos = yd[: nfermi+1]  # y values from negative inf to Fermi
        #use Simpson integration to get d-electron number
        nelectro = simps(dos, E)
        #get total energy of dband
        tot_E = simps(E*dos, E)
        dband_center = tot_E/nelectro
        self.dband_center = dband_center

        return dband_center


class ElfCar(PosCar):
    def __init__(self, filename='ELFCAR'):
        """
        Create a ELFCAR file class.

        Example:

        >>> a = ElfCar()

        Class attributes descriptions
        ==============================================================
          Attribute       Description
          ==============   =============================================
          filename         string, name of the ELFCAR file
          -------------    ame as PosCar ------------
          bases_const      float, lattice bases constant
          bases            np.array, bases of POSCAR
          atoms            list of strings, atom types
          ntot             int, the number of total atom number
          natoms           list of int, same shape with atoms
                           atom number of atoms in atoms
          tf               list of list, T&F info of atoms
          data             np.array, coordinates of atoms, dtype=float64
          -------------    ame as PosCar ------------
          elf_data         3d array
          plot_contour     method, use matplotlib to plot contours
          plot_mcontours   method, use Mayavi.mlab to plot beautiful contour
          plot_contour3d   method, use mayavi.mlab to plot 3d contour
          plot_field       method, plot scalar field for elf data
          ==============  =============================================
        """
        super(self.__class__, self).__init__(filename)

    def load(self):
        "Rewrite load method"
        PosCar.load(self)
        with open(self.filename(), 'r') as f:
            for i in xrange(self.totline):
                f.readline()
            #get dimension of 3d array
            grid = f.readline().strip(whitespace)
            empty = not grid  # empty row
            while empty:
                grid = f.readline().strip(whitespace)
                empty = not grid
            x, y, z = line2list(grid, dtype=int)
            #read electron localization function data
            elf_data = []
            for line in f:
                datalist = line2list(line)
                elf_data.extend(datalist)
        #########################################
        #                                       #
        #           !!! Notice !!!              #
        # NGX is the length of the **0th** axis #
        # NGY is the length of the **1st** axis #
        # NGZ is the length of the **2nd** axis #
        #                                       #
        #########################################
        #reshape to 3d array
        elf_data = np.array(elf_data).reshape((x, y, z), order='F')
        #set attrs
        self.grid = x, y, z
        self.elf_data = elf_data

        return

    @staticmethod
    def expand_data(data, grid, widths):
        '''
        根据widths, 将三维矩阵沿着x, y, z轴方向进行扩展.
        '''
        # expand grid
        widths = np.array(widths)
        expanded_grid = np.array(grid)*widths  # expanded grid
        # expand eld_data matrix
        expanded_data = copy.deepcopy(data)
        nx, ny, nz = widths
        # x axis
        added_data = copy.deepcopy(expanded_data)
        for i in xrange(nx - 1):
            expanded_data = np.append(expanded_data, added_data, axis=0)
        # y axis
        added_data = copy.deepcopy(expanded_data)
        for i in xrange(ny - 1):
            expanded_data = np.append(expanded_data, added_data, axis=1)
        # z axis
        added_data = copy.deepcopy(expanded_data)
        for i in xrange(nz - 1):
            expanded_data = np.append(expanded_data, added_data, axis=2)

        return expanded_data, expanded_grid

    # 装饰器
    def contour_decorator(func):
        '''
        等值线作图方法装饰器.
        Decorator for contour plot methods.
        Set ndim on x, y axis and z values.
        '''
        def contour_wrapper(self, axis_cut='z', distance=0.5,
                            show_mode='show', widths=(1, 1, 1)):
            '''
            绘制ELF等值线图
            Parameter in kwargs
            -------------------
            axis_cut: str
                ['x', 'X', 'y', 'Y', 'z', 'Z'], axis which will be cut.
            distance: float
                (0.0 ~ 1.0), distance to origin
            show_mode: str
                'save' or 'show'
            widths: tuple of int,
                number of replication on x, y, z axis
            '''
            #expand elf_data and grid
            elf_data, grid = self.expand_data(self.elf_data, self.grid,
                                              widths=widths)
            logging.info('data shape = %s', str(elf_data.shape))
            # now cut the cube
            if abs(distance) > 1:
                raise ValueError('Distance must be between 0 and 1.')
            if axis_cut in ['X', 'x']:  # cut vertical to x axis
                nlayer = int(self.grid[0]*distance)
                z = elf_data[nlayer, :, :]
                ndim0, ndim1 = grid[2], grid[1]  # y, z
            elif axis_cut in ['Y', 'y']:
                nlayer = int(self.grid[1]*distance)
                z = elf_data[:, nlayer, :]
                ndim0, ndim1 = grid[2], grid[0]  # x, z
            elif axis_cut in ['Z', 'z']:
                nlayer = int(self.grid[2]*distance)
                z = elf_data[:, :, nlayer]
                ndim0, ndim1 = grid[1], grid[0]  # x, y

            return func(self, ndim0, ndim1, z, show_mode=show_mode)

        return contour_wrapper

    @contour_decorator
    def plot_contour(self, ndim0, ndim1, z, show_mode):
        '''
        ndim0: int, point number on x-axis
        ndim1: int, point number on y-axis
        z    : 2darray, values on plane perpendicular to z axis
        '''
        #do 2d interpolation
        #get slice object
        s = np.s_[0:ndim0:1, 0:ndim1:1]
        x, y = np.ogrid[s]
        logging.info('z shape = %s, x shape = %s, y shape = %s',
                     str(z.shape), str(x.shape), str(y.shape))
        mx, my = np.mgrid[s]
        #use cubic 2d interpolation
        interpfunc = interp2d(x, y, z, kind='cubic')
        newx = np.linspace(0, ndim0, 600)
        newy = np.linspace(0, ndim1, 600)
        #-----------for plot3d---------------------
        ms = np.s_[0:ndim0:600j, 0:ndim1:600j]  # |
        newmx, newmy = np.mgrid[ms]             # |
        #-----------for plot3d---------------------
        newz = interpfunc(newx, newy)

        #plot 2d contour map
        fig2d_1, fig2d_2, fig2d_3 = plt.figure(), plt.figure(), plt.figure()
        ax1 = fig2d_1.add_subplot(1, 1, 1)
        extent = [np.min(newx), np.max(newx), np.min(newy), np.max(newy)]
        img = ax1.imshow(newz, extent=extent, origin='lower')
        #coutour plot
        ax2 = fig2d_2.add_subplot(1, 1, 1)
        cs = ax2.contour(newx.reshape(-1), newy.reshape(-1), newz, 20, extent=extent)
        ax2.clabel(cs)
        plt.colorbar(mappable=img)
        # contourf plot
        ax3 = fig2d_3.add_subplot(1, 1, 1)
        ax3.contourf(newx.reshape(-1), newy.reshape(-1), newz, 20, extent=extent)

        #3d plot
        fig3d = plt.figure(figsize=(12, 8))
        ax3d = fig3d.add_subplot(111, projection='3d')
        ax3d.plot_surface(newmx, newmy, newz, cmap=plt.cm.RdBu_r)

        #save or show
        if show_mode == 'show':
            plt.show()
        elif show_mode == 'save':
            fig2d_1.savefig('surface2d.png', dpi=500)
            fig2d_2.savefig('contour2d.png', dpi=500)
            fig2d_3.savefig('contourf2d.png', dpi=500)
            fig3d.savefig('surface3d.png', dpi=500)
        else:
            raise ValueError('Unrecognized show mode parameter : ' +
                             show_mode)

        return

    @contour_decorator
    def plot_mcontour(self, ndim0, ndim1, z, show_mode):
        "use mayavi.mlab to plot contour."
        if not mayavi_installed:
            logging.info("Mayavi is not installed on your device.")
            return
        #do 2d interpolation
        #get slice object
        s = np.s_[0:ndim0:1, 0:ndim1:1]
        x, y = np.ogrid[s]
        mx, my = np.mgrid[s]
        #use cubic 2d interpolation
        interpfunc = interp2d(x, y, z, kind='cubic')
        newx = np.linspace(0, ndim0, 600)
        newy = np.linspace(0, ndim1, 600)
        newz = interpfunc(newx, newy)
        #mlab
        face = mlab.surf(newx, newy, newz, warp_scale=2)
        mlab.axes(xlabel='x', ylabel='y', zlabel='z')
        mlab.outline(face)
        #save or show
        if show_mode == 'show':
            mlab.show()
        elif show_mode == 'save':
            mlab.savefig('mlab_contour3d.png')
        else:
            raise ValueError('Unrecognized show mode parameter : ' +
                             show_mode)

        return

    def plot_contour3d(self, **kwargs):
        '''
        use mayavi.mlab to plot 3d contour.

        Parameter
        ---------
        kwargs: {
            'maxct'   : float,max contour number,
            'nct'     : int, number of contours,
            'opacity' : float, opacity of contour,
            'widths'   : tuple of int
                        number of replication on x, y, z axis,
        }
        '''
        if not mayavi_installed:
            logging.warning("Mayavi is not installed on your device.")
            return
        # set parameters
        widths = kwargs['widths'] if 'widths' in kwargs else (1, 1, 1)
        elf_data, grid = self.expand_data(self.elf_data, self.grid, widths)
#        import pdb; pdb.set_trace()
        maxdata = np.max(elf_data)
        maxct = kwargs['maxct'] if 'maxct' in kwargs else maxdata
        # check maxct
        if maxct > maxdata:
            logging.warning("maxct is larger than %f", maxdata)
        opacity = kwargs['opacity'] if 'opacity' in kwargs else 0.6
        nct = kwargs['nct'] if 'nct' in kwargs else 5
        # plot surface
        surface = mlab.contour3d(elf_data)
        # set surface attrs
        surface.actor.property.opacity = opacity
        surface.contour.maximum_contour = maxct
        surface.contour.number_of_contours = nct
        # reverse axes labels
        mlab.axes(xlabel='z', ylabel='y', zlabel='x')  # 是mlab参数顺序问题?
        mlab.outline()
        mlab.show()

        return

    def plot_field(self, **kwargs):
        "plot scalar field for elf data"
        if not mayavi_installed:
            logging.warning("Mayavi is not installed on your device.")
            return
        # set parameters
        vmin = kwargs['vmin'] if 'vmin' in kwargs else 0.0
        vmax = kwargs['vmax'] if 'vmax' in kwargs else 1.0
        axis_cut = kwargs['axis_cut'] if 'axis_cut' in kwargs else 'z'
        nct = kwargs['nct'] if 'nct' in kwargs else 5
        widths = kwargs['widths'] if 'widths' in kwargs else (1, 1, 1)
        elf_data, grid = self.expand_data(self.elf_data, self.grid, widths)
        #create pipeline
        field = mlab.pipeline.scalar_field(elf_data)  # data source
        mlab.pipeline.volume(field, vmin=vmin, vmax=vmax)  # put data into volumn to visualize
        #cut plane
        if axis_cut in ['Z', 'z']:
            plane_orientation = 'z_axes'
        elif axis_cut in ['Y', 'y']:
            plane_orientation = 'y_axes'
        elif axis_cut in ['X', 'x']:
            plane_orientation = 'x_axes'
        cut = mlab.pipeline.scalar_cut_plane(
            field.children[0], plane_orientation=plane_orientation)
        cut.enable_contours = True  # 开启等值线显示
        cut.contour.number_of_contours = nct
        mlab.show()
        #mlab.savefig('field.png', size=(2000, 2000))

        return


class ChgCar(ElfCar):
    def __init__(self, filename='CHGCAR'):
        '''
        Create a CHGCAR file class.

        Example:

        >>> a = ChgCar()
        '''
        ElfCar.__init__(self, filename)
