FROM ubuntu:24.04

WORKDIR /workspace

RUN apt-get update
RUN apt-get install -y git vim
RUN apt-get install -y gcc g++ make cmake

# gflags
RUN apt-get install -y libgflags-dev
# glog
RUN apt-get install -y libgoogle-glog-dev
# gtest
RUN apt-get install -y libgtest-dev
