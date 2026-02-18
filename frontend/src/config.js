// src/config.js

const isDevelopment = process.env.NODE_ENV === 'development';

const API_BASE_URL = isDevelopment
  ? 'http://localhost:8000'
  : '';

export { API_BASE_URL };
