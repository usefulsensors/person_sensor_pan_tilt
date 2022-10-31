# Uses the Person Sensor from Useful Sensors to orient a carousel towards the
# nearest face.
# See https://usfl.ink/ps_dev for the full developer guide.

import board
import busio
import pwmio
import struct
import time

from adafruit_motor import servo

# The person sensor has the I2C ID of hex 62, or decimal 98.
PERSON_SENSOR_I2C_ADDRESS = 0x62

# We will be reading raw bytes over I2C, and we'll need to decode them into
# data structures. These strings define the format used for the decoding, and
# are derived from the layouts defined in the developer guide.
PERSON_SENSOR_I2C_HEADER_FORMAT = "BBH"
PERSON_SENSOR_I2C_HEADER_BYTE_COUNT = struct.calcsize(
    PERSON_SENSOR_I2C_HEADER_FORMAT)

PERSON_SENSOR_FACE_FORMAT = "BBBBBBbB"
PERSON_SENSOR_FACE_BYTE_COUNT = struct.calcsize(PERSON_SENSOR_FACE_FORMAT)

PERSON_SENSOR_FACE_MAX = 4
PERSON_SENSOR_RESULT_FORMAT = PERSON_SENSOR_I2C_HEADER_FORMAT + \
    "B" + PERSON_SENSOR_FACE_FORMAT * PERSON_SENSOR_FACE_MAX + "H"
PERSON_SENSOR_RESULT_BYTE_COUNT = struct.calcsize(PERSON_SENSOR_RESULT_FORMAT)

# How long to pause between sensor polls.
PERSON_SENSOR_DELAY = 0.2

# Controls how fast the carousel moves.
PAN_SPEED = 0.1
TILT_SPEED = 0.1

# The Pico doesn't support board.I2C(), so check before calling it. If it isn't
# present then we assume we're on a Pico and call an explicit function.
try:
    i2c = board.I2C()
except:
    i2c = busio.I2C(scl=board.GP5, sda=board.GP4)

# Wait until we can access the bus.
while not i2c.try_lock():
    pass

# Servo setup
pwm_pan_servo = pwmio.PWMOut(board.GP0, duty_cycle=2 ** 15, frequency=50)
pan_servo = servo.Servo(
    pwm_pan_servo, min_pulse=500, max_pulse=2200
)
desired_pan = 90
pan_servo.angle = desired_pan

pwm_tilt_servo = pwmio.PWMOut(board.GP1, duty_cycle=2 ** 15, frequency=50)
tilt_servo = servo.Servo(
    pwm_tilt_servo, min_pulse=500, max_pulse=2200
)
desired_tilt = 90
tilt_servo.angle = desired_tilt

while True:
    read_data = bytearray(PERSON_SENSOR_RESULT_BYTE_COUNT)
    i2c.readfrom_into(PERSON_SENSOR_I2C_ADDRESS, read_data)

    offset = 0
    (pad1, pad2, payload_bytes) = struct.unpack_from(
        PERSON_SENSOR_I2C_HEADER_FORMAT, read_data, offset)
    offset = offset + PERSON_SENSOR_I2C_HEADER_BYTE_COUNT

    (num_faces) = struct.unpack_from("B", read_data, offset)
    num_faces = int(num_faces[0])
    offset = offset + 1

    faces = []
    for i in range(num_faces):
        (box_confidence, box_left, box_top, box_right, box_bottom, id_confidence, id,
         is_facing) = struct.unpack_from(PERSON_SENSOR_FACE_FORMAT, read_data, offset)
        offset = offset + PERSON_SENSOR_FACE_BYTE_COUNT
        face = {
            "box_confidence": box_confidence,
            "box_left": box_left,
            "box_top": box_top,
            "box_right": box_right,
            "box_bottom": box_bottom,
            "id_confidence": id_confidence,
            "id": id,
            "is_facing": is_facing,
        }
        faces.append(face)
    checksum = struct.unpack_from("H", read_data, offset)

    # If we've found any faces, the largest should be the first in the list, so
    # use that to center our servo.
    if num_faces > 0:
        main_face = faces[0]

        face_center_x = (main_face["box_left"] + main_face["box_right"]) / 2
        pan_delta = (face_center_x - 128) * PAN_SPEED
        desired_pan -= pan_delta
        if desired_pan > 180:
            desired_pan = 180
        elif desired_pan < 0:
            desired_pan = 0
        pan_servo.angle = desired_pan

        face_center_y = (main_face["box_top"] + main_face["box_bottom"]) / 2
        tilt_delta = (face_center_y - 128) * TILT_SPEED
        desired_tilt -= tilt_delta
        if desired_tilt > 180:
            desired_tilt = 180
        elif desired_tilt < 0:
            desired_tilt = 0
        tilt_servo.angle = desired_tilt

    time.sleep(0.2)
