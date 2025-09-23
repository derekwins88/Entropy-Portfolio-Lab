FROM node:20-alpine
WORKDIR /srv
COPY tools/mock-server/ ./
RUN npm i --production
EXPOSE 8787
CMD ["node","server.mjs"]
