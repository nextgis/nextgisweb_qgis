RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-key CAEB3DC3BDF7FB45
RUN echo "deb http://qgis.org/debian-ltr xenial main" >> /etc/apt/sources.list