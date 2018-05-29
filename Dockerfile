FROM python:stretch
COPY . .
RUN pip install -r requirements.txt
CMD ["python", "./bot.py"]
