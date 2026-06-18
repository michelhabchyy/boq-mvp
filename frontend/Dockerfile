# Frontend (Next.js) container. Build context: the frontend/ folder.
#
# NEXT_PUBLIC_API_URL is baked into the client bundle at BUILD time, so pass it
# as a build arg:  docker build --build-arg NEXT_PUBLIC_API_URL=https://api.yourco.com -t boq-web .
# (On Vercel you don't need this Dockerfile — just set NEXT_PUBLIC_API_URL in the project env.)

FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build

FROM node:20-alpine AS run
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
EXPOSE 3000
CMD ["sh", "-c", "node server.js"]
