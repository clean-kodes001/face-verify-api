FROM ubuntu:22.04
COPY app /app/
RUN apt update && apt install software-properties-common -y \
&& add-apt-repository ppa:deadsnakes/ppa -y && apt update \
&& apt install python3.10 python3.10-distutils curl libgl1 -y \
&& apt autoremove -y && apt-get clean
RUN curl -sS https://bootstrap.pypa.io/get-pip.py -o get-pip.py && python3.10 get-pip.py
RUN pip install --upgrade pip
COPY app/ /app/
RUN pip install --ignore-installed --no-cache-dir -r /app/requirements.txt
WORKDIR /app
ENV FLASK_RUN_HOST=0.0.0.0
EXPOSE 5000
CMD ["flask", "--app", "main" , "run"]