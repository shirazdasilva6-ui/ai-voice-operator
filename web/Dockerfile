FROM node:24-alpine
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build
# The node image ships an unprivileged `node` user; don't serve as root.
USER node
CMD ["npm", "start"]
