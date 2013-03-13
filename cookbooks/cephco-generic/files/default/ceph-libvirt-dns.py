#!/usr/bin/python
import argparse
import requests
import re
import sys
import time
import datetime
import traceback
import sqlalchemy as sq
import web
import yaml
import libvirt
import json
from lxml import etree
import parser

url = 'http://names.front.sepia.ceph.com:8080/'
domain = 'front.sepia.ceph.com'
sleepinterval = 60

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
    parser.add_argument(
        'remainder',
        nargs=argparse.REMAINDER,
        help='Remainder arguments for webpy, ip:port for listen address'
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

def parseleases(s):
    leases = {}
    for l in parser.parse(s):
        assert 'mac' in l
        leases[l['mac']] = l
    return leases

def add(leases, dburl, name, mac):
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

    ip = leases[mac]['ip']
    existcheck = sq.select([records_table], records_table.c.name==name).limit(1).execute().fetchone()
    if existcheck is None:
        state = "Added"
        ins = records_table.insert()
        db.execute(ins, domain_id=my_domain_id, name=name, type="A", content=ip, ttl="30", auth="1")
    else:
        if existcheck[4] == ip:
            state = "No Change"
        else:
            state = "Updated"
            records_table.update().where(records_table.c.name==name).values(content=ip).execute()
    returnstring = "                 " + state + " HOSTNAME: "+name+" MAC: "+mac+" IP: "+ip
    return returnstring

class index:
    def GET(self):
        i = web.input()
        s = open(web.leasefile).read()
        leases = parseleases(s)
        string = ''
        for guest in i:
            if '|' not in  i[guest]:
                print "Client sent junk data"
            else:
                name = i[guest].split('|')[0]
                mac = i[guest].split('|')[1]
                hostname = name + '.' + domain
                if mac in leases:
                    string = string + '\n' + add(leases, web.dburl, name=hostname, mac=mac)
                else:
                    string = "Error: IP for: " + name + " not found from MAC: " + mac
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


def _handle_event(conn, domain, event, detail, getstring):
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
            getstring = getstring + name + '=' + name + '|' + mac + '&'
    return getstring


def libvirt_list_and_update_dns():
    uri = 'qemu:///system'
    try:
        conn = libvirt.openReadOnly(uri)
    except Exception:
        print "Something went wrong connecting to libvirt. Is libvirt-bin installed/running? Sleeping for 5 minutes"
        time.sleep(300)
        return
        pass

    getstring = ''

    for domain in getAllDomains(conn):
        getstring = _handle_event(
            conn=conn,
            domain=domain,
            event=libvirt.VIR_DOMAIN_EVENT_DEFINED,
            detail=None,
            getstring=getstring
            )

    getstring = getstring.rstrip('&')

    if getstring == '':
        print "Host has no guests with front network bridging. Not contacting server."
        return

    try:
        update = requests.get(url + '?' + getstring)
    except Exception:
        print "Contacting the server failed. Is it down?  Sleeping for 5 minutes"
        time.sleep(300)
        return

    try:
        exception = update.raise_for_status()
    except Exception:
        print "Server response was abnormal (non 200) Sleeping for 5 minutes"
        traceback.print_exc()
        time.sleep(300)
        return

    print 'Server Response:'+update.content

def main():
    args = parse_args()

    if args.server:
        print "Running in Server Mode:"
        config = read_config(args.config)
        web.dburl = config['database']
        web.leasefile = config['leasefile']
        # Webpy also uses Arguments. Replace sys.argv with argument 0 (script name) and add unused arguments by argparse)
        sys.argv = [sys.argv[0]] + args.remainder
        app = web.application(urls, globals())
        app.run()
    else:
        print "Running in Client Mode:"
        while True:
            print datetime.datetime.now()
            libvirt_list_and_update_dns()
            print "Sleeping for "+str(sleepinterval)+" Seconds..."
            time.sleep(sleepinterval)

if __name__ == "__main__":
    main()
