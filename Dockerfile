# Use a lightweight Nginx image
FROM nginx:alpine

# Remove default Nginx static assets
RUN rm -rf /usr/share/nginx/html/*

# Copy your HTML and database to the Nginx serving directory
COPY index.html /usr/share/nginx/html/
COPY repo_sync_state.db /usr/share/nginx/html/

# Expose port 80 inside the container
EXPOSE 80

# Nginx starts automatically