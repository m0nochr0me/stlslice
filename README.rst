stlslice
========

Simple slicer for DLP/SLA 3D printers.

Reuirements
-----------
 - python3
 - pipenv

Installation
------------

Install ``pipenv``:

Ubuntu 17.10::

    $ sudo apt install software-properties-common python-software-properties
    $ sudo add-apt-repository ppa:pypa/ppa
    $ sudo apt update
    $ sudo apt install pipenv

Archlinux::

    $ sudo pacman -Sy python-pipenv

Distribution independent::

    $ sudo pip install pipenv

You probably need to add your user to the following groups: ``uucp``, ``dialout``, ``tty``::

    $ sudo usermod -a -G uucp *username*
    $ sudo usermod -a -G tty *username*
    $ sudo usermod -a -G dialout *username*

Install::

    $ git clone https://bitbucket.org/m0nochr0me/stlslice.git
    $ cd stlslice
    $ pipenv --python 3
    $ pipenv install numpy pillow vtk opencv-python

Usage
-----

Run::

    $ pipenv run python stlslice.py -s myfile.stl -i -l 0.1 -p 2
