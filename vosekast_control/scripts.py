import subprocess
import asyncio
from vosekast_control.main import main


def backend(emulate=False):
    asyncio.run(main(emulate=emulate))


def frontend():
    subprocess.call("cd frontend && yarn start", shell=True)


def build():
    print("Build frontend for app:")
    subprocess.call("cd frontend && yarn build", shell=True)


def start():
    print("Start vosekast in production mode:")
    backend()


def dev():
    print("Start vosekast in dev mode:")
    frontend()
    backend(emulate=False)


def dev_backend():
    print("Start the backend alone:")
    backend(emulate=False)


def dev_frontend():
    print("Start the frontend standalone:")
    frontend()


def test():
    print("Run test:")
    subprocess.call("pytest ./test", shell=True)
