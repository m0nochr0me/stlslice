import os
import cv2
import vtk
import sys
import lzma
import math
import tarfile
import argparse
import tempfile
import numpy as np
from vtk.util import numpy_support
from PIL import Image, ImageDraw, ImageOps


#  .d88b.  d8888b. d888888b d888888b  .d88b.  d8b   db .d8888.
# .8P  Y8. 88  `8D `~~88~~'   `88'   .8P  Y8. 888o  88 88'  YP
# 88    88 88oodD'    88       88    88    88 88V8o 88 `8bo.
# 88    88 88~~~      88       88    88    88 88 V8o88   `Y8b.
# `8b  d8' 88         88      .88.   `8b  d8' 88  V888 db   8D
#  `Y88P'  88         YP    Y888888P  `Y88P'  VP   V8P `8888Y'


parser = argparse.ArgumentParser(description='STLslice - simple slicer for DLP/DUP 3D printers')
parser.add_argument("-s",
                  dest="filename",
                  type=str,
                  metavar="FILE",
                  help=" to slice")
parser.add_argument("-l",
                  dest="layerheight",
                  default=0.1,
                  type=float,
                  help="Layer height (mm)")
parser.add_argument("-i",
                  dest="ignorebad",
                  action="store_true",
                  help="Ignore bad polygons")
parser.add_argument("-p",
                  dest="padding",
                  default=1,
                  type=int,
                  help="Slice image paadding (mm)")
parser.add_argument("-t",
                  dest="threshold",
                  default=10,
                  type=int,
                  help="Bad poly closing threshold")
parser.add_argument("-v",
                  "--verbose",
                  dest="verbose",
                  action="store_true",
                  help="Verbose output")
parser.add_argument("--xmirror",
                  dest="xmirror",
                  action="store_true",
                  help="Mirror X axis")
parser.add_argument("--yup",
                  dest="yup",
                  action="store_true",
                  help="Y up")
parser.add_argument("-d",
                  dest="dpmm",
                  metavar=('DPMM_X', 'DPMM_X'),
                  nargs=2,
                  type=float,
                  default=(21.16402, 21.16402),
                  help="Pixel per mm x y")
parser.add_argument("--gif",
                  dest="gif",
                  action="store_true",
                  help="Use GIF output")

options= parser.parse_args()
if options.filename is None:
    parser.print_help()
    sys.exit(1)

# d888888b d8b   db d888888b d888888b
#   `88'   888o  88   `88'   `~~88~~'
#    88    88V8o 88    88       88
#    88    88 V8o88    88       88
#   .88.   88  V888   .88.      88
# Y888888P VP   V8P Y888888P    YP


dpmm = options.dpmm
dpi = (dpmm[0] * 25.4, dpmm[1] * 25.4)

# load stl
model = vtk.vtkSTLReader()
model.SetFileName(options.filename)
model.ScalarTagsOn()
model.Update()

# create transformation matrix
mirror = vtk.vtkTransform()
mirrorfilter = vtk.vtkTransformFilter()
mirrorfilter.SetInputConnection(model.GetOutputPort())
mirrorfilter.SetTransform(mirror)

# mirror model by Y axis
mirror.Scale(1, -1, 1)

if options.xmirror:
    mirror.Scale(-1, 1, 1)

mirrorfilter.Update()

rotate = vtk.vtkTransform()
rotatefilter = vtk.vtkTransformFilter()
rotatefilter.SetInputConnection(mirrorfilter.GetOutputPort())
rotatefilter.SetTransform(rotate)

if options.yup:
    rotate.RotateX(-90)

rotatefilter.Update()

# model bounds
bounds = rotatefilter.GetOutput().GetBounds()
print(bounds)

# model size
dimX = bounds[1] - bounds[0]
dimY = bounds[3] - bounds[2]
dimZ = bounds[5] - bounds[4]

if options.verbose:
    print("Model dimenstions: ", dimX, dimY, dimZ)

translate = vtk.vtkTransform()
translatefilter = vtk.vtkTransformFilter()
translatefilter.SetInputConnection(rotatefilter.GetOutputPort())
translatefilter.SetTransform(translate)

# reset origin
translate.Translate(-bounds[0], -bounds[2], -bounds[4])

translatefilter.Update()

# copy poly data of modified model
# mdlpd = transform.GetOutput()
polydata = vtk.vtkPolyData()
polydata.DeepCopy(translatefilter.GetOutput())

# apply connectivity filter
cf = vtk.vtkPolyDataConnectivityFilter()
cf.SetInputData(polydata)
cf.SetExtractionModeToAllRegions()
cf.ScalarConnectivityOff()
cf.ColorRegionsOn()
cf.Update()

# threshold filter
tf = vtk.vtkThreshold()
tf.SetInputConnection(cf.GetOutputPort())

# cutting plane
plane = vtk.vtkPlane()
plane.SetOrigin(0, 0, 0)
plane.SetNormal(0, 0, 1)

# cutter
cutter = vtk.vtkCutter()
cutter.SetInputConnection(tf.GetOutputPort())
cutter.SetCutFunction(plane)
cutter.SetValue(0, 0)
cutter.Update()

# stripper
stripper = vtk.vtkStripper()
stripper.SetInputConnection(cutter.GetOutputPort())
stripper.Update()


# .d8888. db      d888888b  .o88b. d88888b
# 88'  YP 88        `88'   d8P  Y8 88'
# `8bo.   88         88    8P      88ooooo
#   `Y8b. 88         88    8b      88~~~~~
# db   8D 88booo.   .88.   Y8b  d8 88.
# `8888Y' Y88888P Y888888P  `Y88P' Y88888P


def Slice(layerheight):
    currentz = layerheight
    layerscount = math.floor(dimZ / layerheight)
    partscount = cf.GetNumberOfExtractedRegions()

    layers = []
    for n in range(layerscount):
        if options.verbose:
            print("Slicing layer: ", n, '/', layerscount)
        parts = []
        for k in range(partscount):
            tf.ThresholdBetween(k, k)
            cutter.SetValue(0, currentz)
            stripper.Update()

            cut = stripper.GetOutput()

            pointsraw = cut.GetPoints()
            linesraw = cut.GetLines()
            ncel = linesraw.GetNumberOfCells()
            points = numpy_support.vtk_to_numpy(pointsraw.GetData())
            lines = numpy_support.vtk_to_numpy(linesraw.GetData())

            # remove z coordinate
            points = points[:, 0:2]

            # set DPI
            points[:, 0] *= dpmm[0]
            points[:, 1] *= dpmm[1]

            # lists of polygon indexes
            polygood = []
            polybad = []
            polyerr = []
            index = 0

            # process polygon indexes and append it to corresponding list
            for i in range(ncel):
                # number of points in subpolygon
                npts = lines[index]
                # subpoly indexes
                spi = lines[index+1:index+npts+1]
                # check if polygon good or bad
                if spi[0] == spi[-1]:
                    polygood.append(spi)
                else:
                    polybad.append(spi)
                index += npts+1
            badpolycount = len(polybad)
            if options.verbose and polybad:
                print("Bad polygons: {}".format(badpolycount))
            match = [False for i in range(badpolycount)]
            for i in range(badpolycount):
                if match[i] is not True:
                    A = polybad[i]
                    run = True
                    while run:
                        run = False
                        closed = False
                        for j in range(badpolycount):
                            if i != j and match[j] is False:
                                B = polybad[j]

                                # attempt to close polygons
                                if A[0] == B[0]:
                                    match[j] = True
                                    A = np.insert(A, 0, np.flip(B[1:], axis=0))
                                    if A[0] == A[-1]:
                                        polygood.append(A)
                                        run = False
                                        closed = True
                                        break
                                    else:
                                        run = True

                                elif A[-1] == B[0]:
                                    match[j] = True
                                    A = np.append(A, B[1:])
                                    if A[0] == A[-1]:
                                        polygood.append(A)
                                        run = False
                                        closed = True
                                        break
                                    else:
                                        run = True

                                elif A[0] == B[-1]:
                                    match[j] = True
                                    A = np.insert(A, 0, B[:-1])
                                    if A[0] == A[-1]:
                                        polygood.append(A)
                                        run = False
                                        closed = True
                                        break
                                    else:
                                        run = True

                                elif A[-1] == B[-1]:
                                    match[j] = True
                                    A = np.insert(A, 0, np.flip(B[:-1], axis=0))
                                    if A[0] == A[-1]:
                                        polygood.append(A)
                                        run = False
                                        closed = True
                                        break
                                    else:
                                        run = True

                        if run is False and closed is False:
                            start = points[A[0]]
                            end = points[A[-1]]
                            dist = math.sqrt((start[0] - end[0])**2 + (start[1] - end[1])**2)
                            if options.verbose:
                                print("Bad polygon at Z = {}".format(currentz))
                            polyerr.append(A)
                            if options.ignorebad or dist < options.threshold:
                                polygood.append(A)

            polygons = []
            for pind in polygood:
                pc = []
                for i in pind:
                    pc.append(points[i])
                pc = np.array(pc)
                polygons.append(pc)
            parts.append(polygons)

        currentz += layerheight
        layers.append(parts)

    return layers

# .d8888.  .d8b.  db    db d88888b
# 88'  YP d8' `8b 88    88 88'
# `8bo.   88ooo88 Y8    8P 88ooooo
#   `Y8b. 88~~~88 `8b  d8' 88~~~~~
# db   8D 88   88  `8bd8'  88.
# `8888Y' YP   YP    YP    Y88888P


def Save(layers):
    h = math.ceil(dimX * dpmm[0])
    w = math.ceil(dimY * dpmm[1])
    padding = math.ceil(options.padding * dpmm[0])
    n = 0
    layerscount = len(layers)
    tmpdir = tempfile.TemporaryDirectory(prefix="stlslice-")
    os.makedirs(tmpdir.name + '/slices')
    for layer in layers:
        if options.verbose:
            print("Saving layer: ", n, '/', layerscount)
        imcv = np.zeros([w, h], dtype=np.uint8)
        for part in layer:
            pt = [np.array(np.multiply(poly, 2**3), dtype=np.int32) for poly in part]
            cv2.fillPoly(imcv, pt, color=255, shift=3, lineType=cv2.LINE_AA)
        impil = Image.fromarray(imcv)
        imexp = ImageOps.expand(impil, padding)
        if options.gif:
            imexp.save("{}/slices/layer-{}.gif".format(tmpdir.name, n), "GIF", optimize=True)
        else:
            imexp.save("{}/slices/layer-{}.png".format(tmpdir.name, n), "PNG", dpi=dpi)
        n += 1
    archfile = "{}.txz".format(options.filename)
    # archfile = "{}-{}x{}-{}mm.txz".format(options.filename, *dpmm, options.layerheight)
    outfile = lzma.LZMAFile(archfile, mode='w')
    with tarfile.open(mode='w', fileobj=outfile) as xz:
        xz.add(tmpdir.name, arcname=archfile)
    outfile.close()

# -----------------------------------------------------------------------------

if __name__ == "__main__":
    layers = Slice(options.layerheight)
    Save(layers)
