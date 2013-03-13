package 'python-webpy'
package 'python-requests'
package 'python-sqlalchemy'
package 'python-mysqldb'
package 'python-yaml'
package 'python-lxml'
package 'python-pyparsing'

execute "Create ceph-libvirt-dns dir" do
  command <<-EOH
  mkdir -p /srv/inktank.com/ceph-libvirt-dns
  EOH
end

cookbook_file '/srv/inktank.com/ceph-libvirt-dns/ceph-libvirt-dns.py' do
  source "ceph-libvirt-dns.py"
  mode 0755
  owner "root"
  group "root"
end

cookbook_file '/srv/inktank.com/ceph-libvirt-dns/parser.py' do
  source "parser.py"
  mode 0755
  owner "root"
  group "root"
end

cookbook_file '/etc/init/ceph-libvirt-dns.conf' do
  source "ceph-libvirt-dns.conf"
  mode 0755
  owner "root"
  group "root"
end

execute "Start ceph-libvirt-dns service" do
  command <<-EOH
  start ceph-libvirt-dns
  EOH
end

