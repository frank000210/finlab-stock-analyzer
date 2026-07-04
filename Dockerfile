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

# Install Python dependencies.
# TA-Lib used to require compiling the C library from source (wget the
# sourceforge tarball, configure/make/install, then pip-build the Python
# wrapper against it) -- that toolchain broke twice in a row on this base
# image's newer gcc-14 (a numpy 2.x ABI mismatch, then a promoted-to-error
# pointer-type warning; see git history on this file). TA-Lib>=0.6 ships
# prebuilt manylinux wheels (cp311, glibc 2.17+/2.28+ x86_64) with the C
# library statically bundled in the wheel, so plain `pip install` now just
# downloads a binary wheel -- no gcc/g++/make/wget, no source build, no
# compiler-flag workarounds needed at all.
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir TA-Lib==0.6.8

# Copy backend code
COPY backend/ ./backend/

# Copy frontend build
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

ENV PYTHONPATH=/app/backend
ENV PORT=8080
EXPOSE 8080

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
