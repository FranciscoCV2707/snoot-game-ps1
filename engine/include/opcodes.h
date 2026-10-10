/* Generado por tools/engine/gen_opcodes.py: no editar a mano. */
#pragma once

#define OP_NOP 0x00
#define OP_SAY 0x01
#define OP_SAYX 0x02
#define OP_TEXTBOX 0x03
#define OP_SCENE 0x10
#define OP_SHOW 0x11
#define OP_HIDE 0x12
#define OP_TRANSITION 0x13
#define OP_SHOW_RANDOM 0x14
#define OP_MARK_SEEN 0x15
#define OP_CAMERA 0x16
#define OP_BACKGROUND 0x17
#define OP_ORDER 0x18
#define OP_MUSIC_PLAY 0x20
#define OP_MUSIC_STOP 0x21
#define OP_AMBIENT_PLAY 0x22
#define OP_AMBIENT_STOP 0x23
#define OP_SFX_PLAY 0x24
#define OP_SFX_STOP 0x25
#define OP_VOLUME 0x26
#define OP_MUSIC_QUEUE 0x27
#define OP_PAUSE 0x30
#define OP_SPECIAL 0x31
#define OP_MENU 0x40
#define OP_JUMP 0x41
#define OP_JUMP_IF_FALSE 0x42
#define OP_CALL 0x43
#define OP_RETURN 0x44
#define OP_LOAD_CHAPTER 0x45
#define OP_END 0x46
#define OP_SET_VAR 0x50
#define OP_ADD_VAR 0x51
#define OP_PUSH_VAR 0x52
#define OP_PUSH_CONST 0x53
#define OP_OP 0x54
#define OP_STORE_VAR 0x55
#define OP_LOAD_PACK 0x60
#define OP_UNLOCK_BONUS 0x61
#define OP_ENDING 0x62
#define OP_DEBUG 0xFE
#define OP_HALT 0xFF

typedef struct {
	const char *name;
	const char *fmt;     /* B u8, b s8, H u16, h s16, I u32; NULL = longitud variable (MENU) */
	int nfields;
} OpInfo;

static const OpInfo *op_info(int code)
{
	switch (code) {
	case OP_NOP: { static const OpInfo i = { "NOP", "", 0 }; return &i; }
	case OP_SAY: { static const OpInfo i = { "SAY", "BH", 2 }; return &i; }
	case OP_SAYX: { static const OpInfo i = { "SAYX", "BH", 2 }; return &i; }
	case OP_TEXTBOX: { static const OpInfo i = { "TEXTBOX", "B", 1 }; return &i; }
	case OP_SCENE: { static const OpInfo i = { "SCENE", "HH", 2 }; return &i; }
	case OP_SHOW: { static const OpInfo i = { "SHOW", "BHBbBH", 6 }; return &i; }
	case OP_HIDE: { static const OpInfo i = { "HIDE", "B", 1 }; return &i; }
	case OP_TRANSITION: { static const OpInfo i = { "TRANSITION", "BHHH", 4 }; return &i; }
	case OP_SHOW_RANDOM: { static const OpInfo i = { "SHOW_RANDOM", "BHBB", 4 }; return &i; }
	case OP_MARK_SEEN: { static const OpInfo i = { "MARK_SEEN", "H", 1 }; return &i; }
	case OP_CAMERA: { static const OpInfo i = { "CAMERA", "HhhHB", 5 }; return &i; }
	case OP_BACKGROUND: { static const OpInfo i = { "BACKGROUND", "H", 1 }; return &i; }
	case OP_ORDER: { static const OpInfo i = { "ORDER", "BBB", 3 }; return &i; }
	case OP_MUSIC_PLAY: { static const OpInfo i = { "MUSIC_PLAY", "HBB", 3 }; return &i; }
	case OP_MUSIC_STOP: { static const OpInfo i = { "MUSIC_STOP", "B", 1 }; return &i; }
	case OP_AMBIENT_PLAY: { static const OpInfo i = { "AMBIENT_PLAY", "BHB", 3 }; return &i; }
	case OP_AMBIENT_STOP: { static const OpInfo i = { "AMBIENT_STOP", "BB", 2 }; return &i; }
	case OP_SFX_PLAY: { static const OpInfo i = { "SFX_PLAY", "H", 1 }; return &i; }
	case OP_SFX_STOP: { static const OpInfo i = { "SFX_STOP", "B", 1 }; return &i; }
	case OP_VOLUME: { static const OpInfo i = { "VOLUME", "BBB", 3 }; return &i; }
	case OP_MUSIC_QUEUE: { static const OpInfo i = { "MUSIC_QUEUE", "H", 1 }; return &i; }
	case OP_PAUSE: { static const OpInfo i = { "PAUSE", "HB", 2 }; return &i; }
	case OP_SPECIAL: { static const OpInfo i = { "SPECIAL", "B", 1 }; return &i; }
	case OP_MENU: { static const OpInfo i = { "MENU", NULL, 2 }; return &i; }
	case OP_JUMP: { static const OpInfo i = { "JUMP", "I", 1 }; return &i; }
	case OP_JUMP_IF_FALSE: { static const OpInfo i = { "JUMP_IF_FALSE", "I", 1 }; return &i; }
	case OP_CALL: { static const OpInfo i = { "CALL", "I", 1 }; return &i; }
	case OP_RETURN: { static const OpInfo i = { "RETURN", "", 0 }; return &i; }
	case OP_LOAD_CHAPTER: { static const OpInfo i = { "LOAD_CHAPTER", "HIB", 3 }; return &i; }
	case OP_END: { static const OpInfo i = { "END", "", 0 }; return &i; }
	case OP_SET_VAR: { static const OpInfo i = { "SET_VAR", "Bh", 2 }; return &i; }
	case OP_ADD_VAR: { static const OpInfo i = { "ADD_VAR", "Bh", 2 }; return &i; }
	case OP_PUSH_VAR: { static const OpInfo i = { "PUSH_VAR", "B", 1 }; return &i; }
	case OP_PUSH_CONST: { static const OpInfo i = { "PUSH_CONST", "h", 1 }; return &i; }
	case OP_OP: { static const OpInfo i = { "OP", "B", 1 }; return &i; }
	case OP_STORE_VAR: { static const OpInfo i = { "STORE_VAR", "B", 1 }; return &i; }
	case OP_LOAD_PACK: { static const OpInfo i = { "LOAD_PACK", "H", 1 }; return &i; }
	case OP_UNLOCK_BONUS: { static const OpInfo i = { "UNLOCK_BONUS", "B", 1 }; return &i; }
	case OP_ENDING: { static const OpInfo i = { "ENDING", "B", 1 }; return &i; }
	case OP_DEBUG: { static const OpInfo i = { "DEBUG", "H", 1 }; return &i; }
	case OP_HALT: { static const OpInfo i = { "HALT", "", 0 }; return &i; }
	default: return 0;
	}
}

#define OPERATOR_COUNT 12
/* orden: == != < <= > >= and or not + - * */

#define OPR_0 0  /* == */
#define OPR_1 1  /* != */
#define OPR_2 2  /* < */
#define OPR_3 3  /* <= */
#define OPR_4 4  /* > */
#define OPR_5 5  /* >= */
#define OPR_6 6  /* and */
#define OPR_7 7  /* or */
#define OPR_8 8  /* not */
#define OPR_9 9  /* + */
#define OPR_10 10  /* - */
#define OPR_11 11  /* * */
