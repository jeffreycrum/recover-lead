FROM node:20-alpine AS build

WORKDIR /app

COPY frontend/package.json frontend/package-lock.json* ./
RUN npm install

COPY frontend/ .

ARG VITE_API_URL
ARG VITE_CLERK_PUBLISHABLE_KEY
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_CLERK_PUBLISHABLE_KEY=$VITE_CLERK_PUBLISHABLE_KEY

RUN npm run build

FROM node:20-alpine

WORKDIR /app
RUN npm install -g serve
COPY --from=build /app/dist ./dist

CMD sh -c "serve -s dist -l ${PORT:-3000}"
