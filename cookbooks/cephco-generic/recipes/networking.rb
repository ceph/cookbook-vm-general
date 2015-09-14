package 'ethtool'
package 'bridge-utils'


front_mac = IO.popen('ifconfig eth0 | grep -i hwadd | awk "{print \$5}"').read.chop
back_mac = IO.popen('ifconfig eth2 | grep -i hwadd | awk "{print \$5}"').read.chop

front_ip = IO.popen('ip addr show dev eth0 | grep -w inet | awk "{print \$2}" | cut -d"/" -f1').read.chop
back_ip = IO.popen('ip addr show dev eth2 | grep -w inet | awk "{print \$2}" | cut -d"/" -f1').read.chop

need_run = ! File.open('/etc/network/interfaces').read() =~ /br-front/

GENERIC_MACS = {
  node['hostname'] => {
    '1g1' => front_mac,
    '10g1' => back_mac,
  },
}

GENERIC_IPS = {
  node['hostname'] => {
    'front' => front_ip,
    'back' => back_ip,
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
  source 'interfaces.erb'
  mode 0644
  variables(
            'macs' => GENERIC_MACS[node['hostname']],
            'ips' => GENERIC_IPS[node['hostname']],
            )
  only_if need_run
end

execute "activate network config" do
   command <<-'EOH'
     set -e
     ifdown -a
     mv /etc/network/interfaces.chef /etc/network/interfaces
     ifup -a
  EOH
  # don't run the ifdown/ifup if there's no change to the file
  only_if {need_run && "cmp /etc/network/interfaces.chef /etc/network/interfaces"}
end
