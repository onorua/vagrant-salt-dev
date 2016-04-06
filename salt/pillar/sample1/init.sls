# -*- coding: utf-8 -*-
# vim: ft=yaml

# Defaults can be overwritten, see sample1/default.yaml and sample1/map.jinja
#    for default values
#
# sample1:
#   lookup:
#     repo_dir: '/root/foobar' # This is the directory to store all repos
#     user: 'root' # This is the user to own all the directories

sample1:
  repo:
    tools:
      url: https://github.com/jgartrel/codereview-tools.git
      rev: master
    example_project:
      url: https://github.com/jgartrel/project1.git
