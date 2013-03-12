package 'qemu-kvm'
package 'libvirt-bin'
package 'virtinst'
package 'ebtables'
package 'python-vm-builder'

include_recipe "cephco-generic::ssh-keys"

if node['hostname'].match(/^mira/)
  include_recipe "cephco-generic::networking-mira"
else
  include_recipe "cephco-generic::networking"
end

include_recipe "cephco-generic::libvirt"
include_recipe "cephco-generic::libvirt-dns"
