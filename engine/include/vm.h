/*
 * Maquina virtual del bytecode VNB (docs/bytecode.md). Codigo portable: no usa nada de la PS1, asi que tambien se
 * compila en la PC para compararlo contra el simulador de Python (tests/test_vm_host.py).
 *
 * Uso: vm_init; luego vm_run en bucle. vm_run ejecuta hasta un evento que necesita al anfitrion (texto, menu, pausa,
 * transicion, fin). Las demas instrucciones se aplican a la escena y se avisan por host->notify.
 */
#pragma once

#include <stdint.h>

#define VM_MAX_SPRITES 16
#define VM_STACK 16
#define VM_CALLS 8
#define VM_VARS 64
#define VM_MENU_MAX 16
#define VM_Z_KEEP (-128)

typedef struct {
	const uint8_t *code;        /* inicio del codigo (el .VNB cargado + 32) */
	uint32_t code_size;
	uint32_t text_base;         /* id global del primer texto del capitulo */
	uint16_t text_count;
	uint16_t anim_count;
	const uint8_t *anims;       /* tabla ANIM o NULL */
} VmChapter;

#define VM_SPRITE_RANDOM 0x04       /* flag de SHOW_RANDOM: aparece y se desvanece en (rx, ry) como randPosition */

typedef struct {
	uint8_t used, tag, pos, flags;
	int8_t z;
	uint16_t image, anim;
	uint32_t born;              /* orden de creacion (desempata el z) */
	uint32_t shown_at;          /* vm->now cuando empezo su animacion */
	int16_t rx, ry;             /* alineacion 8.8 de los sprites de SHOW_RANDOM */
} VmSprite;

typedef enum {
	VM_EV_NONE = 0,
	VM_EV_SAY,          /* vm->ev_speaker, ev_text, ev_gid, ev_extend */
	VM_EV_MENU,         /* vm->menu_*; el anfitrion pone vm->choice y vuelve a llamar vm_run */
	VM_EV_PAUSE,        /* vm->ev_frames, ev_flags */
	VM_EV_TRANSITION,   /* vm->ev_args[0..3] */
	VM_EV_SPECIAL,      /* vm->ev_args[0] */
	VM_EV_END,
	VM_EV_ERROR
} VmEvent;

typedef struct Vm Vm;

typedef struct {
	void *user;
	/* Carga un capitulo (blocking). Devuelve 0 si salio bien. */
	int (*load_chapter)(void *user, int chapter, VmChapter *out);
	/* Aviso de una instruccion ya aplicada: opcode y sus campos en orden. */
	void (*notify)(void *user, int opcode, const int32_t *args, int nargs);
} VmHost;

struct Vm {
	const VmHost *host;
	VmChapter ch;
	int chapter;
	uint32_t pc;
	int16_t vars[VM_VARS];
	int16_t stack[VM_STACK];
	int sp;
	struct { int chapter; uint32_t pc; } calls[VM_CALLS];
	int ncalls;

	/* escena */
	uint16_t bg, bg_anim;
	VmSprite sprites[VM_MAX_SPRITES];
	uint32_t born_counter;

	/* datos del evento actual */
	int ev_speaker, ev_text, ev_gid, ev_extend;
	int ev_frames, ev_flags;
	int32_t ev_args[4];
	int menu_n, menu_flags;
	int menu_text[VM_MENU_MAX];
	uint32_t menu_target[VM_MENU_MAX];
	int choice;                 /* lo pone el anfitrion al resolver un menu */
	int in_menu;
	const char *error;
	uint32_t now;               /* reloj del anfitrion en cuadros (inicio de las animaciones) */
	uint32_t rng;               /* estado del azar de SHOW_RANDOM */
};

void vm_init(Vm *vm, const VmHost *host);
/* Empieza a ejecutar el capitulo `chapter` en el offset `entry`. Devuelve 0 si salio bien. */
int vm_start(Vm *vm, int chapter, uint32_t entry);
VmEvent vm_run(Vm *vm);
/* Sprite por tag (NULL si no existe) */
VmSprite *vm_sprite(Vm *vm, int tag);
