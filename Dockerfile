FROM python:3.11

COPY ./requirements.txt /tmp/
WORKDIR /tmp
RUN pip install -r requirements.txt
WORKDIR /src/vegeshop
CMD ["python", "manage.py", "runserver"]
