import http.client
import ipaddress
import json
import socket
import threading
import time

import pytest

from mjpeg_server import (
    BOUNDARY,
    BrokerClosed,
    FrameBroker,
    LatestFrameEncoder,
    MjpegServer,
    local_ipv4,
    stream_url,
)


def wait_until(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    return False


@pytest.fixture
def running_server():
    broker = FrameBroker()
    server = MjpegServer(broker, lambda: {"rotation": 90, "width": 640, "height": 480}, ports=(0,), host="127.0.0.1")
    server.start()
    yield broker, server
    server.stop()


def get(port, path):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request("GET", path)
    response = conn.getresponse()
    body = response.read()
    conn.close()
    return response, body


def read_part(response):
    boundary_line = response.fp.readline()
    assert boundary_line.strip() == b"--" + BOUNDARY
    headers = {}
    while True:
        line = response.fp.readline().strip()
        if not line:
            break
        name, value = line.split(b":", 1)
        headers[name.strip().lower()] = value.strip()
    assert headers[b"content-type"] == b"image/jpeg"
    body = response.fp.read(int(headers[b"content-length"]))
    assert response.fp.read(2) == b"\r\n"
    return body


def test_broker_wait_next_returns_new_frame():
    broker = FrameBroker()
    threading.Timer(0.05, broker.publish, args=(b"A",)).start()
    assert broker.wait_next(0, timeout=2) == (1, b"A")


def test_broker_wait_next_times_out():
    assert FrameBroker().wait_next(0, timeout=0.05) is None


def test_broker_close_wakes_waiters():
    broker = FrameBroker()
    threading.Timer(0.05, broker.close).start()
    with pytest.raises(BrokerClosed):
        broker.wait_next(0, timeout=2)


def test_broker_counts_clients():
    broker = FrameBroker()
    with broker.client():
        with broker.client():
            assert broker.clients == 2
    assert broker.clients == 0


def test_page_links_stream(running_server):
    _, server = running_server
    response, body = get(server.port, "/")
    assert response.status == 200
    assert response.getheader("Content-Type").startswith("text/html")
    assert b"/stream.mjpg" in body
    assert b"/info.json" in body


def test_info_reports_rotation_size_and_clients(running_server):
    _, server = running_server
    response, body = get(server.port, "/info.json")
    assert response.status == 200
    assert json.loads(body) == {"rotation": 90, "width": 640, "height": 480, "clients": 0}


def test_snapshot_unavailable_then_available(running_server):
    broker, server = running_server
    response, _ = get(server.port, "/snapshot.jpg")
    assert response.status == 503
    broker.publish(b"\xff\xd8jpeg\xff\xd9")
    response, body = get(server.port, "/snapshot.jpg")
    assert response.status == 200
    assert response.getheader("Content-Type") == "image/jpeg"
    assert body == b"\xff\xd8jpeg\xff\xd9"


def test_unknown_path_is_404(running_server):
    _, server = running_server
    response, _ = get(server.port, "/nope")
    assert response.status == 404


def test_stream_delivers_frames_and_tracks_clients(running_server):
    broker, server = running_server
    broker.publish(b"frame-1")
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    conn.request("GET", "/stream.mjpg")
    response = conn.getresponse()
    assert response.status == 200
    assert response.getheader("Content-Type") == f"multipart/x-mixed-replace; boundary={BOUNDARY.decode()}"
    assert read_part(response) == b"frame-1"
    assert broker.clients == 1
    broker.publish(b"frame-2")
    assert read_part(response) == b"frame-2"
    # HTTPResponse tiene aperto il socket anche dopo conn.close().
    response.close()
    conn.close()
    # Il server se ne accorge solo alla scrittura successiva.
    assert wait_until(lambda: (broker.publish(b"x" * 65536), broker.clients == 0)[1])


def test_stop_closes_open_streams():
    broker = FrameBroker()
    server = MjpegServer(broker, dict, ports=(0,), host="127.0.0.1")
    server.start()
    conn = http.client.HTTPConnection("127.0.0.1", server.port, timeout=5)
    conn.request("GET", "/stream.mjpg")
    response = conn.getresponse()
    assert wait_until(lambda: broker.clients == 1)
    server.stop()
    assert response.read() == b""
    assert wait_until(lambda: broker.clients == 0)
    conn.close()


def test_falls_back_to_next_free_port():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        busy_port = busy.getsockname()[1]
        server = MjpegServer(FrameBroker(), dict, ports=(busy_port, 0), host="127.0.0.1")
        port = server.start()
        try:
            assert port != busy_port
        finally:
            server.stop()


def test_raises_when_no_port_is_free():
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        server = MjpegServer(FrameBroker(), dict, ports=(busy.getsockname()[1],), host="127.0.0.1")
        with pytest.raises(OSError):
            server.start()


def test_rejects_empty_port_list():
    with pytest.raises(ValueError):
        MjpegServer(FrameBroker(), dict, ports=()).start()


def test_encoder_publishes_latest_and_drops_stale():
    broker = FrameBroker()
    gate = threading.Event()

    def slow_encode(item):
        gate.wait(2)
        return item

    encoder = LatestFrameEncoder(broker, slow_encode, max_fps=1000)
    encoder.start()
    encoder.submit(b"first")
    time.sleep(0.05)
    for i in range(5):
        encoder.submit(b"f%d" % i)
    gate.set()
    assert wait_until(lambda: broker.latest() == b"f4")
    assert encoder.dropped == 4
    encoder.stop()


def test_encoder_respects_max_fps():
    broker = FrameBroker()
    encoder = LatestFrameEncoder(broker, lambda item: item, max_fps=10)
    encoder.start()
    end = time.monotonic() + 0.55
    while time.monotonic() < end:
        encoder.submit(b"frame")
        time.sleep(0.005)
    encoder.stop()
    assert 4 <= encoder.encoded <= 7


def test_encoder_survives_encode_errors_and_runs_exit_hook():
    broker = FrameBroker()
    exited = threading.Event()

    def encode(item):
        if item == b"bad":
            raise RuntimeError("guasto")
        return item

    encoder = LatestFrameEncoder(broker, encode, max_fps=1000, on_thread_exit=exited.set)
    encoder.start()
    encoder.submit(b"bad")
    time.sleep(0.05)
    encoder.submit(b"good")
    assert wait_until(lambda: broker.latest() == b"good")
    encoder.stop()
    assert exited.is_set()


def test_encoder_ignores_submit_when_stopped():
    broker = FrameBroker()
    encoder = LatestFrameEncoder(broker, lambda item: item, max_fps=10)
    encoder.submit(b"frame")
    encoder.stop()
    assert broker.latest() is None


def test_encoder_rejects_non_positive_fps():
    with pytest.raises(ValueError):
        LatestFrameEncoder(FrameBroker(), lambda item: item, max_fps=0)


def test_local_ipv4_is_private_or_none():
    ip = local_ipv4()
    if ip is not None:
        assert not ipaddress.ip_address(ip).is_loopback


def test_local_ipv4_none_when_all_probes_fail():
    assert local_ipv4(probe_addresses=("not-an-address.invalid",)) is None


def test_stream_url():
    assert stream_url("192.168.1.23", 8080) == "http://192.168.1.23:8080/"
