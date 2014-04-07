import re
import sys
import subprocess
from prettytable import PrettyTable
from pathlib import Path

from pprint import pprint

REGEXP_CONTROLLER_HP = re.compile(r'Smart Array ([A-Z0-9]+) in Slot ([0-9]+)')
REGEXP_RAID_ARRAY = re.compile(r'Array: ([A-Z]+)')
REGEXP_PHYSICAL_DRIVE = re.compile(r'physicaldrive ([A-Z0-9]+:[0-9]+:[0-9]+)$')
REGEXP_PHYSICAL_DRIVE_SERIAL = re.compile(r'Serial Number: (.*)')
REGEXP_LOGICAL_DRIVE = re.compile(r'Logical Drive: ([0-9]+)')
REGEXP_ERROR = re.compile(r'Error: (.*)', re.M)
REGEXP_DISK_NAME = re.compile(r'Disk Name: (.*)')

DEBUG = False
ZFS_SUPPORT = False

def bootstrap():
    process = subprocess.Popen('lsmod | grep zfs | wc -l', shell=True,
                     stdout=subprocess.PIPE,
                     stderr=subprocess.PIPE)
    out, err = process.communicate()
    if int(out.strip()) > 0:
        global ZFS_SUPPORT
        ZFS_SUPPORT = True

def find_vdev(device):
    p = Path('/dev/disk/by-vdev')
    for child in p.iterdir():
        if child.resolve() == Path(device):
            return str(child)
    return None

def parse_hpacucli(content):
    content = content.split('\n')

    controllers = []
    controller = None
    array = None
    pdrive = None
    ldrive = None

    for line in content:
        result = REGEXP_CONTROLLER_HP.search(line)
        if result:
            controller = {
                    'type': result.group(1),
                    'slot': result.group(2),
                    'arrays': [],
                    }
            controllers.append(controller)
            ldrive = None
            pdrive = None

        result_array = REGEXP_RAID_ARRAY.search(line)
        if controller and result_array:
            array_identifier = result_array.groups(1)[0]
            array = {
                'identifier': array_identifier,
                'ld': [],
                }

            controller['arrays'].append(array)

        result_ldrive = REGEXP_LOGICAL_DRIVE.search(line)
        if array != None and \
                result_ldrive:
            ldrive_identifier = result_ldrive.groups(1)[0]
            ldrive = {
                'identifier': ldrive_identifier,
                'disk_name': None,
                'pd': [],
                }
            array['ld'].append(ldrive)

        result_diskname = REGEXP_DISK_NAME.search(line)
        if ldrive != None and \
                result_diskname:
            disk_name = result_diskname.groups(1)[0]
            if ldrive:
                ldrive['disk_name'] = disk_name
                if ZFS_SUPPORT:
                    ldrive['vdev'] = find_vdev(disk_name)

        result_pdrive = REGEXP_PHYSICAL_DRIVE.search(line)
        if ldrive != None and \
                result_pdrive:
            pdrive_identifier = result_pdrive.groups(1)[0]
            pdrive = {
                'identifier': pdrive_identifier,
                }
            ldrive['pd'].append(pdrive)


        result_pdrive_serial = REGEXP_PHYSICAL_DRIVE_SERIAL.search(line)
        if pdrive and \
                result_pdrive_serial:
            pdrive_serial = result_pdrive_serial.groups(1)[0]
            pdrive['serial_number'] = pdrive_serial

    return controllers

def pretty_print(controllers):
    columns = []
    controllers_row = ['%(type)s Slot: %(slot)s' % {
            'type': x['type'],
            'slot': x['slot'],
            } for x in controllers]

    x = PrettyTable(controllers_row)
    for controller in controllers:
        column = []
        columns.append(column)
        for array in controller['arrays']:
            column_content = ''
            for ld in array['ld']:
                column_content += '%(device)s\n'  % {
                    'device': ld['disk_name'].replace('/dev/', '')
                    }
                if ZFS_SUPPORT:
                    column_content += '%(vdev)s\n' % {
                        'vdev': ld['vdev'].replace('/dev/disk/by-vdev/', '')
                        }
                for pd in ld['pd']:
                    column_content += '%(pd_identifier)s\n' % {'pd_identifier': pd['identifier']}
            column.append(column_content)
        column_content = None

    for row in zip(*columns):
        x.add_row(row)
    print x


def main():
    bootstrap()

    cmd = "hpacucli ctrl all show config detail"
    process = subprocess.Popen(cmd, shell=True,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    out, err = process.communicate()

    controllers = parse_hpacucli(out)
    if DEBUG:
        pprint(controllers)
    pretty_print(controllers)

if __name__ == '__main__':
    main()
