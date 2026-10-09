"""Tabla de instrucciones del bytecode VNB (ver docs/bytecode.md). Compartida por compilador, desensamblador y simulador."""
import struct

VERSION = b"VNB1"

# nombre -> (opcode, formato struct little-endian de los argumentos, nombres de los campos)
OPS = {
    "NOP": (0x00, "", ()),
    "SAY": (0x01, "BH", ("speaker", "text")),
    "SAYX": (0x02, "BH", ("speaker", "text")),
    "TEXTBOX": (0x03, "B", ("mode",)),
    "SCENE": (0x10, "H", ("image",)),
    "SHOW": (0x11, "BHBbBH", ("tag", "image", "pos", "z", "flags", "anim")),
    "HIDE": (0x12, "B", ("tag",)),
    "TRANSITION": (0x13, "BHHH", ("type", "a", "b", "c")),
    "SHOW_RANDOM": (0x14, "BHBB", ("tag", "first", "count", "flags")),
    "MARK_SEEN": (0x15, "H", ("image",)),
    "MUSIC_PLAY": (0x20, "HBB", ("track", "fade", "flags")),
    "MUSIC_STOP": (0x21, "B", ("fade",)),
    "AMBIENT_PLAY": (0x22, "BHB", ("slot", "sound", "fade")),
    "AMBIENT_STOP": (0x23, "BB", ("slot", "fade")),
    "SFX_PLAY": (0x24, "H", ("sound",)),
    "SFX_STOP": (0x25, "B", ("fade",)),
    "VOLUME": (0x26, "BBB", ("channel", "volume", "time")),
    "MUSIC_QUEUE": (0x27, "H", ("track",)),
    "PAUSE": (0x30, "HB", ("frames", "flags")),
    "SPECIAL": (0x31, "B", ("id",)),
    "MENU": (0x40, None, ("flags", "choices")),   # flags u8, n u8, n x (texto u16, destino u32)
    "JUMP": (0x41, "I", ("target",)),
    "JUMP_IF_FALSE": (0x42, "I", ("target",)),
    "CALL": (0x43, "I", ("target",)),
    "RETURN": (0x44, "", ()),
    "LOAD_CHAPTER": (0x45, "HIB", ("chapter", "entry", "mode")),   # mode 0 = call, 1 = jump
    "END": (0x46, "", ()),
    "SET_VAR": (0x50, "Bh", ("var", "value")),
    "ADD_VAR": (0x51, "Bh", ("var", "value")),
    "PUSH_VAR": (0x52, "B", ("var",)),
    "PUSH_CONST": (0x53, "h", ("value",)),
    "OP": (0x54, "B", ("op",)),
    "STORE_VAR": (0x55, "B", ("var",)),
    "LOAD_PACK": (0x60, "H", ("pack",)),
    "UNLOCK_BONUS": (0x61, "B", ("n",)),
    "ENDING": (0x62, "B", ("id",)),
    "DEBUG": (0xFE, "H", ("id",)),
    "HALT": (0xFF, "", ()),
}
BY_CODE = {code: (name, fmt, fields) for name, (code, fmt, fields) in OPS.items()}
JUMP_OPS = {"JUMP", "JUMP_IF_FALSE", "CALL"}

OPERATORS = ["==", "!=", "<", "<=", ">", ">=", "and", "or", "not", "+", "-", "*"]
OP_CODE = {name: i for i, name in enumerate(OPERATORS)}

TRANSITION_NAMES = {0: "cut", 1: "dissolve", 2: "fade", 3: "vpunch", 4: "hpunch"}
SAY_SPEAKER_NARRATOR = 0
FLAG_FLIP = 1
FLAG_HIDDEN = 2
Z_KEEP = -128
POS_NONE = 255


def size_of(name, args=None):
    fmt = OPS[name][1]
    if name == "MENU":
        return 3 + 6 * len(args["choices"])
    return 1 + struct.calcsize("<" + fmt)
