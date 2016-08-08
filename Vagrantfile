# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|

  config.vm.define "master", primary: true do |master|
    master.vm.box = "geerlingguy/ubuntu1604"
    master.vm.hostname = "master01"
    master.vm.network "private_network", ip: "192.168.33.10"
    master.vm.synced_folder "salt/roots", "/srv/salt/"
    master.vm.synced_folder "salt/pillar", "/srv/pillar"
    master.vm.provision :salt do |salt|
        salt.install_master = true
        salt.grains_config = "salt/master_grains.yaml"
        salt.minion_key = "salt/pki/minion.pem"
        salt.minion_pub = "salt/pki/minion.pub"
        salt.master_key = "salt/pki/master.pem"
        salt.master_pub = "salt/pki/master.pub"
        salt.seed_master = 
        {
           master01: "salt/pki/minion.pub",
           node01: "salt/pki/node01.pub"
        }
        salt.minion_config = "salt/master01.yml"
        salt.run_highstate = false
        
        salt.colorize = true
        salt.log_level = 'info'
    end
    master.vm.provision "shell", inline: "sudo salt-call state.highstate"
  end

  config.vm.define "node01" do |node01|
    node01.vm.box = "geerlingguy/ubuntu1604"
    node01.vm.hostname = "node01"
    node01.vm.network "private_network", ip: "192.168.33.101"
    node01.vm.provision :salt do |salt|
        salt.grains_config = "salt/node_grains.yaml"
        salt.minion_key = "salt/pki/node01.pem"
        salt.minion_pub = "salt/pki/node01.pub"
        salt.run_highstate = true
        salt.minion_config = "salt/node01.yml"
        
        salt.colorize = true
        salt.log_level = 'info'
    end

  end
                              
  config.vm.provider "virtualbox" do |vb|
    vb.memory = "1048"
    vb.cpus = 1
  end

end
