#!/usr/bin/python
import argparse
import requests
import re
import sys
import time
import datetime

url = 'http://10.99.118.26:8080/'
domain = 'front.sepia.ceph.com'
sleepinterval = 30

def parse_args():
    parser = argparse.ArgumentParser(
        description='DNS for libvirt',
        )
    parser.add_argument(
        '--config',
        metavar='CONFIGFILE',
        help='path to YAML config file',
        )
    parser.add_argument(
        '--server',
        action='store_true', default=False,
        help='Run as the server (http/sql access).',
        )
    args = parser.parse_args()
    return args

def read_config(path):
    if path is None:
        raise NameError('Configuration file not specified with --config or cant be opened')
    else:
        with file(path) as f:
            obj = yaml.safe_load(f)
        assert 'config' in obj
        return obj['config']


urls = (
    '/', 'index'
)

def add(leasefile, dburl, name, mac):
    my_domain_id = 1
    db = sq.create_engine(dburl)
    metadata = sq.MetaData(bind=db)
    records_table = sq.Table('records', metadata,
                        sq.Column('id', sq.Integer, primary_key=True),
                        sq.Column('domain_id', sq.Integer),
                        sq.Column('name', sq.String),
                        sq.Column('type', sq.String),
                        sq.Column('content', sq.String),
                        sq.Column('ttl', sq.Integer),
                        sq.Column('prio', sq.Integer),
                        sq.Column('change_date', sq.Integer),
                        sq.Column('ordername', sq.String),
                        sq.Column('auth', sq.Integer),
                        sq.Column('propernoun_epoch', sq.Integer),
                        )

    #Search for IP in DHCP leases
    leases = open(leasefile).readlines()
    ip = None
    r = re.compile(mac)
    for i in range(len(leases)):
        if r.search(leases[i]):
            ip=leases[max(0, i-6)].strip().split(' ')[1]

    if ip is None:
        returnstring = "Error: IP address not found from mac "+mac
        return returnstring
    else:
        existcheck = sq.select([records_table], records_table.c.name==name).limit(1).execute().fetchone()
        if existcheck is None:
            state = "Added"
            ins = records_table.insert()
            db.execute(ins, domain_id=my_domain_id, name=name, type="A", content=ip, ttl="30", auth="1")
        else:
            state = "Updated"
            records_table.update().where(records_table.c.name==name).values(content=ip).execute()
        returnstring = state+" hostname:"+name+" Mac:"+mac+" IP:"+ip
        return returnstring

class index:
    def GET(self):
        i = web.input(name=None, mac=None)
        if i.name is None:
            string = "Nothing to do with received Data. Please send name and mac values in a GET request..."
        else:
            hostname=i.name+"."+domain
            string=add(web.leasefile, web.dburl, name=hostname, mac=i.mac)
        return string



def getAllDomains(conn):
    """
    List and get all domains, active or not.

    The python bindings don't seem to have this at version
    0.9.8-2ubuntu17.1 and a combination of listDefinedDomains and
    listDomainsID is just miserable.

    http://libvirt.org/html/libvirt-libvirt.html#virConnectListAllDomains

    Also fetch the actual domain object, as we'll need the xml.
    """
    for name in conn.listDefinedDomains():
        try:
            domain = conn.lookupByName(name)
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_DOMAIN:
                # lost a race, someone undefined the domain
                # between listing names and fetching details
                pass
            else:
                raise
        else:
            yield domain

    for id_ in conn.listDomainsID():
        try:
            domain = conn.lookupByID(id_)
        except libvirt.libvirtError as e:
            if e.get_error_code() == libvirt.VIR_ERR_NO_DOMAIN:
                # lost a race, someone undefined the domain
                # between listing names and fetching details
                pass
            else:
                raise
        else:
            yield domain


def get_interfaces(tree):
    networks = tree.xpath(
        "/domain/devices/interface[@type='network']",
        )
    for net in networks:
        (name,) = net.xpath('./source/@network')
        (mac,) = net.xpath('./mac/@address')
        yield (name, mac)


def _handle_event(conn, domain, event, detail):
    msg = dict(
        type='libvirt',
        vm=dict(
            name=domain.name(),
            uuid=domain.UUIDString(),
            ),
        )
    if event == libvirt.VIR_DOMAIN_EVENT_DEFINED:
        xml_s = domain.XMLDesc(flags=0)
        tree = etree.fromstring(xml_s)
        ifaces = get_interfaces(tree)
        ifaces = list(ifaces)
        msg['vm']['interfaces'] = ifaces
    elif event == libvirt.VIR_DOMAIN_EVENT_UNDEFINED:
        pass
    else:
        print >>sys.stderr, \
            ('unknown event:'
             + ' Domain {name} event={event} detail={detail}'.format(
                    name=domain.name(),
                    event=event,
                    detail=detail,
                    )
             )
        return
    for int in ifaces:
        if 'front' in int:
            name = domain.name()
            mac = int[1]
            update = requests.get(url+'?name='+name+'&mac='+mac)
            update.raise_for_status()
            print 'Server Response: '+update.content

def libvirtlist():
    uri = 'qemu:///system'
    try:
        conn = libvirt.openReadOnly(uri)
    except Exception:
        print "Something went wrong connecting to libvirt. Is libvirt-bin installed/running? Sleeping for 5 minutes"
        time.sleep(500)
        return
        pass
    for domain in getAllDomains(conn):
        _handle_event(
            conn=conn,
            domain=domain,
            event=libvirt.VIR_DOMAIN_EVENT_DEFINED,
            detail=None,
            )

if __name__ == "__main__":
    args = parse_args()

    if args.server:
        import sqlalchemy as sq
        import web
        import yaml

        print "Running in Server Mode:"
        config = read_config(args.config)
        web.dburl = config['database']
        web.leasefile = config['leasefile']

        sys.argv = [s for s in sys.argv if s not in ('--server', '--config', args.config)]
        app = web.application(urls, globals())
        app.run()
    else:
        print "Running in Client Mode:"
        import libvirt
        import json
        from lxml import etree
        while True:
            print datetime.datetime.now()
            libvirtlist()
            print "Sleeping for "+str(sleepinterval)+" Seconds..."
            time.sleep(sleepinterval)

