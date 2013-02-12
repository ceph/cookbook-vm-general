package 'qemu-kvm'
package 'libvirt-bin'
package 'virtinst'
package 'ebtables'
package 'python-vm-builder'

include_recipe "cephco-generic::ssh-keys"
include_recipe "cephco-generic::serial"
include_recipe "cephco-generic::networking"
include_recipe "cephco-generic::libvirt"
