# vagrant-salt-dev

This repo is a development sandbox for Saltstack with Vagrant. It provides a baseline development environment and sample code to begin creating salt modules and testing those modules within Vagrant.  This repo can also be used to seed a new development project and provide a Vagrant test environment for that project.


## Getting started

Bootstrapping the new VM is easy once Vagrant is installed.  Simply follow the following steps:
```
vagrant up --provider virtualbox
vagrant ssh     # This gives you a terminal in the VM
cd /vagrant     # This is a link to this repo directory mounted in the VM
```

To remove your VM, simply run:
```
vagrant destroy
```


## Running Salt

Salt will be run by automatically when the VM boots.  To run Salt again simply use the following command:
```
sudo salt-call state.highstate --retcode-passthrough  --log-level=info --force-color
```

Other useful Salt commands are as follows:
```
sudo salt-call grains.items
sudo salt-call pillar.items
```


## Developing Salt Formulas

An example formula has been provided here: [salt/roots/sample1](salt/roots/sample1/).  This formula has four main components:

1. Main formula file: [sample1/init.sls](salt/roots/sample1/init.sls)
  This is where the bulk of the Salt 'code' should reside.  This is the file that does the bulk of the actual work.
2. Default parameters: [sample1/default.yaml](salt/roots/sample1/default.yaml)
  In this file we store default parameters used by the init.sls Salt formula.
3. OS specific parameters: [sample1/map.jinja](salt/roots/sample1/map.jinja)
  This file merges OS specific parameters into the default parameters.  It as merges in any pillar configuration specified in the 'sample1:lookup' pillar.
4. Pillar data and examples: [pillar.example](salt/pillar/sample1/init.sls) for sample1
  Normally this data is stored in pillars in the Salt 'master', however in this development environment all pillar data is specified locally in [salt/pillar](salt/pillar/) to ease the development process.

The formula and pillar configuration referenced above should provide a baseline e for developing and testing new formulas.


## Vagrant specific information

The included [Vagrantfile](Vagrantfile) will start a new VM, bootstrap salt, and run the include formulas.

1. It specifies a 'hostname':

    ```
    config.vm.hostname = "vagrant-salt-dev"
    ```

2. The Vagrantfile will mount the Salt formula root and Pillar data:

    ```
    config.vm.synced_folder "salt/roots/", "/srv/salt/"
    config.vm.synced_folder "salt/pillar/", "/srv/pillar/"
    ```

3. Finally it bootstraps and invokes salt in 'standalone' mode in [salt/minion.yml](salt/minion.yml):

    ```
    config.vm.provision :salt do |salt|
      salt.minion_config = "salt/minion.yml"
      salt.run_highstate = true
      salt.colorize = true
      salt.log_level = 'info'
    end
    ```

The 'hostname' is pre-appended with 'vagrant-' which causes Salt via [salt/pillar/top.sls](salt/pillar/top.sls) to load the Vagrant specific pillar information provided in [salt/pillar/vagrant/init.sls](salt/pillar/vagrant/init.sls).  Any Vagrant VM specific Salt configuraiton should be added to this file.
