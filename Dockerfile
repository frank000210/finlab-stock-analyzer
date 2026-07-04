# Build frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# Python backend
FROM python:3.11-slim
WORKDIR /app

# Install TA-Lib C library and build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ make wget && \
    wget -q http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib && ./configure --prefix=/usr && make && make install && \
    cd .. && rm -rf ta-lib ta-lib-0.4.0-src.tar.gz

# Install Python dependencies (while gcc is still available for TA-Lib wheel)
COPY backend/requirements.txt ./
# TA-Lib's C wrapper is built against whatever numpy pip's *isolated* build
# environment happens to grab (numpy 2.x today), not the numpy==1.26.4 we
# just installed above -- and TA-Lib 0.4.28 is compiled against the numpy
# 1.x C-API (PyArray_Descr layout changed in 2.0), so an isolated build
# fails with "error: 'PyArray_Descr' {aka 'struct _PyArray_Descr'} has no
# member named ...". --no-build-isolation makes it reuse the numpy already
# installed in this environment instead of fetching a fresh, incompatible one.
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --no-build-isolation TA-Lib==0.4.28 && \
    apt-get remove -y gcc g++ make wget && apt-get autoremove -y && \
    rm -rf /var/lib/apt/lists/*

# Copy backend code
COPY backend/ ./backend/

# Copy frontend build
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

ENV PYTHONPATH=/app/backend
ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
