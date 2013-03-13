package 'ethtool'
package 'bridge-utils'


if File.open('/etc/network/interfaces').read() =~ /br-front/
 raise "This recipe has already been ran on this machine. Exiting..."
end

front_mac = IO.popen('ifconfig eth0 | grep -i hwadd | awk "{print \$5}"').read.chop

front_ip = IO.popen('ip addr show dev eth0 | grep -w inet | awk "{print \$2}" | cut -d"/" -f1').read.chop

GENERIC_MACS = {
  node['hostname'] => {
    '1g1' => front_mac,
  },
}

GENERIC_IPS = {
  node['hostname'] => {
    'front' => front_ip,
  },
}

cookbook_file '/etc/network/rename-if-by-mac' do
  backup false
  owner 'root'
  group 'root'
  mode 0755
end


# generate a .chef file from a template, and then be extra careful in
# swapping it in place; effecting changes over ssh is DANGEROUS,
# please have a serial console handy
template '/etc/network/interfaces.chef' do
  source 'interfaces-mira.erb'
  mode 0644
  variables(
            'macs' => GENERIC_MACS[node['hostname']],
            'ips' => GENERIC_IPS[node['hostname']],
            )
end

execute "activate network config" do
   command <<-'EOH'
     set -e
     ifdown -a
     mv /etc/network/interfaces.chef /etc/network/interfaces
     ifup -a
  EOH
  # don't run the ifdown/ifup if there's no change to the file
  not_if "cmp /etc/network/interfaces.chef /etc/network/interfaces"
end
