FROM python:3.14-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY core/      core/
COPY static/    static/
COPY templates/ templates/
COPY app.py     .

EXPOSE 4653
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "4653"]
