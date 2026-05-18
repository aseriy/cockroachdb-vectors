# Takara local models

Load the docker image into the local registry:

```bash
docker load -i your-image-file.tar.gz
```

```bash
docker tag 287493837598.dkr.ecr.us-west-1.amazonaws.com/dev-ds1-fukuro:latest localhost:5000/dev-ds1-fukuro:latest
```

Push to the local registry:

```bash
docker push localhost:5000/dev-ds1-fukuro:latest
```

View Entrypoint and Default Commands

```bash
$ docker inspect localhost:5000/dev-ds1-fukuro:latest | jq '.[0].Config | {Entrypoint, Cmd}'
{
  "Entrypoint": [
    "./entrypoint.sh"
  ],
  "Cmd": null
}
```

Check Environment Variables & Ports

```bash
$ docker inspect localhost:5000/dev-ds1-fukuro:latest | jq '.[0].Config.Env'
[
  "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
  "HUGGINGFACE_HUB_CACHE=/data",
  "PORT=8080",
  "MODEL_ID=Takara-DS1/ds1-fukuro",
  "MAX_BATCH_TOKENS=200000"
]
```


```bash
docker run -d \
  --name ds1-fukuro-test \
  -p 8080:8080 \
  localhost:5000/dev-ds1-fukuro:latest
```

```bash
docker logs ds1-fukuro-test
```

```bash
curl -s http://localhost:8080/
```


```bash
nuctl deploy takara-ds1-fukuro --platform kube --namespace nuclio --registry 172.31.28.245:5000 --run-registry localhost:5000 -f models/takara_ds1_fukuro.yaml -p models/takara_ds1_fukuro.py --project-name cockroachdb
```

