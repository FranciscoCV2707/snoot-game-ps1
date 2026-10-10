#include <string.h>
#include "opcodes.h"
#include "vm.h"

#define MAX_FIELDS 8

static uint16_t rd16(const uint8_t *p)
{
	return (uint16_t)(p[0] | (p[1] << 8));
}

static uint32_t rd32(const uint8_t *p)
{
	return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
}

/* Lee los campos de una instruccion de longitud fija segun su formato. Devuelve los bytes consumidos (sin el opcode). */
static int decode_fields(const char *fmt, const uint8_t *p, int32_t *out)
{
	int n = 0, off = 0;

	for (; *fmt; fmt++, n++) {
		switch (*fmt) {
		case 'B': out[n] = p[off]; off += 1; break;
		case 'b': out[n] = (int8_t)p[off]; off += 1; break;
		case 'H': out[n] = rd16(p + off); off += 2; break;
		case 'h': out[n] = (int16_t)rd16(p + off); off += 2; break;
		case 'I': out[n] = (int32_t)rd32(p + off); off += 4; break;
		}
	}
	return off;
}

void vm_init(Vm *vm, const VmHost *host)
{
	memset(vm, 0, sizeof(*vm));
	vm->host = host;
	vm->rng = 12345;
}

int vm_start(Vm *vm, int chapter, uint32_t entry)
{
	if (vm->host->load_chapter(vm->host->user, chapter, &vm->ch) != 0)
		return -1;
	vm->chapter = chapter;
	vm->pc = entry;
	vm->sp = 0;
	vm->ncalls = 0;
	return 0;
}

VmSprite *vm_sprite(Vm *vm, int tag)
{
	int i;

	for (i = 0; i < VM_MAX_SPRITES; i++)
		if (vm->sprites[i].used && vm->sprites[i].tag == tag)
			return &vm->sprites[i];
	return 0;
}

static VmEvent fail(Vm *vm, const char *msg)
{
	vm->error = msg;
	return VM_EV_ERROR;
}

static int push(Vm *vm, int v)
{
	if (vm->sp >= VM_STACK)
		return -1;
	vm->stack[vm->sp++] = (int16_t)v;
	return 0;
}

static void apply_op(Vm *vm, int op)
{
	int b, a, r = 0;

	if (op == 8) {                 /* not */
		vm->stack[vm->sp - 1] = vm->stack[vm->sp - 1] ? 0 : 1;
		return;
	}
	b = vm->stack[--vm->sp];
	a = vm->stack[--vm->sp];
	switch (op) {
	case 0: r = a == b; break;
	case 1: r = a != b; break;
	case 2: r = a < b; break;
	case 3: r = a <= b; break;
	case 4: r = a > b; break;
	case 5: r = a >= b; break;
	case 6: r = (a && b) ? 1 : 0; break;
	case 7: r = (a || b) ? 1 : 0; break;
	case 9: r = a + b; break;
	case 10: r = a - b; break;
	case 11: r = a * b; break;
	}
	vm->stack[vm->sp++] = (int16_t)r;
}

static void clear_scene(Vm *vm)
{
	memset(vm->sprites, 0, sizeof(vm->sprites));
}

static void scene_show(Vm *vm, const int32_t *a)
{
	VmSprite *s = vm_sprite(vm, a[0]);
	int i, existing = s != 0;

	if (!s) {
		for (i = 0; i < VM_MAX_SPRITES && vm->sprites[i].used; i++)
			;
		if (i == VM_MAX_SPRITES)
			return;                          /* demasiados sprites: se ignora (el simulador avisa antes) */
		s = &vm->sprites[i];
		s->used = 1;
		s->tag = (uint8_t)a[0];
		s->z = (int8_t)(a[3] == VM_Z_KEEP ? 0 : a[3]);
		s->born = ++vm->born_counter;
	} else if (a[3] != VM_Z_KEEP) {
		s->z = (int8_t)a[3];
	}
	s->image = (uint16_t)a[1];
	/* 254 = conservar posicion y animacion; 255 (sin "at") en un sprite que ya estaba tambien las conserva, como Ren'Py */
	if (a[2] != 254 && !(a[2] == 255 && existing && a[5] == 0)) {
		s->pos = (uint8_t)a[2];
		s->anim = (uint16_t)a[5];
		s->shown_at = vm->now;
		s->sound_t = -1;
	}
	s->flags = (uint8_t)a[4];
}

static int vm_random(Vm *vm, int n)
{
	vm->rng = vm->rng * 1103515245u + 12345u;
	return (int)((vm->rng >> 16) % (uint32_t)n);
}

/* showCG(): una de `count` imagenes desde `first` en una alineacion al azar entre 0.2 y 0.8 (randPosition) */
static void scene_show_random(Vm *vm, const int32_t *a)
{
	int32_t show[6];
	VmSprite *s;

	show[0] = a[0];
	show[1] = a[1] + vm_random(vm, a[2]);
	show[2] = 255;
	show[3] = VM_Z_KEEP;
	show[4] = VM_SPRITE_RANDOM;
	show[5] = 0;
	scene_show(vm, show);
	s = vm_sprite(vm, a[0]);
	if (s) {
		s->anim = 0;
		s->shown_at = vm->now;
		s->rx = (int16_t)(51 + vm_random(vm, 154));
		s->ry = (int16_t)(51 + vm_random(vm, 154));
	}
}

/* `show tag behind ref` de Ren'Py: tag pasa justo detras de ref si estaba por encima (con above, justo encima). */
static void scene_order(Vm *vm, int tag, int ref, int above)
{
	VmSprite *s = vm_sprite(vm, tag), *r = vm_sprite(vm, ref);
	uint32_t at;
	int i;

	if (!s || !r || s == r)
		return;
	if (!above && (s->z < r->z || (s->z == r->z && s->born < r->born)))
		return;
	at = above ? r->born + 1 : r->born;
	for (i = 0; i < VM_MAX_SPRITES; i++)
		if (vm->sprites[i].used && vm->sprites[i].born >= at)
			vm->sprites[i].born++;
	vm->born_counter++;
	s->born = at;
	s->z = r->z;
}

VmEvent vm_run(Vm *vm)
{
	int steps = 0;

	if (vm->in_menu) {                           /* se resuelve el menu pendiente */
		vm->in_menu = 0;
		if (vm->choice < 0 || vm->choice >= vm->menu_n)
			return fail(vm, "opcion de menu invalida");
		vm->pc = vm->menu_target[vm->choice];
	}

	for (;;) {
		const uint8_t *p;
		const OpInfo *info;
		int32_t a[MAX_FIELDS];
		int op, used = 0;

		if (++steps > 4000000)
			return fail(vm, "posible bucle infinito");
		if (vm->pc >= vm->ch.code_size)
			return fail(vm, "pc fuera de rango");
		p = vm->ch.code + vm->pc;
		op = p[0];
		info = op_info(op);
		if (!info)
			return fail(vm, "opcode invalido");

		if (op == OP_MENU) {
			int n = p[2], i;

			vm->menu_flags = p[1];
			vm->menu_n = n > VM_MENU_MAX ? VM_MENU_MAX : n;
			for (i = 0; i < vm->menu_n; i++) {
				vm->menu_text[i] = rd16(p + 3 + 6 * i);
				vm->menu_target[i] = rd32(p + 5 + 6 * i);
			}
			vm->pc += 3 + 6 * n;
			vm->in_menu = 1;
			if (vm->host->notify) {
				int32_t m[2 + VM_MENU_MAX];
				m[0] = vm->menu_flags;
				m[1] = vm->menu_n;
				for (i = 0; i < vm->menu_n; i++)
					m[2 + i] = vm->menu_text[i];
				vm->host->notify(vm->host->user, OP_MENU, m, 2 + vm->menu_n);
			}
			return VM_EV_MENU;
		}

		used = decode_fields(info->fmt, p + 1, a);
		vm->pc += 1 + used;

		switch (op) {
		case OP_SAY:
		case OP_SAYX:
			if (a[1] >= vm->ch.text_count)
				return fail(vm, "texto fuera de rango");
			vm->ev_speaker = a[0];
			vm->ev_text = a[1];
			vm->ev_gid = (int)(vm->ch.text_base + a[1]);
			vm->ev_extend = (op == OP_SAYX);
			if (vm->host->notify)
				vm->host->notify(vm->host->user, op, a, info->nfields);
			return VM_EV_SAY;
		case OP_PAUSE:
			vm->ev_frames = a[0];
			vm->ev_flags = a[1];
			if (vm->host->notify)
				vm->host->notify(vm->host->user, op, a, info->nfields);
			return VM_EV_PAUSE;
		case OP_TRANSITION:
			memcpy(vm->ev_args, a, sizeof(int32_t) * 4);
			if (vm->host->notify)
				vm->host->notify(vm->host->user, op, a, info->nfields);
			return VM_EV_TRANSITION;
		case OP_SPECIAL:
			vm->ev_args[0] = a[0];
			if (vm->host->notify)
				vm->host->notify(vm->host->user, op, a, info->nfields);
			return VM_EV_SPECIAL;
		case OP_END:
			return VM_EV_END;
		case OP_HALT:
			return fail(vm, "HALT");

		case OP_SCENE:
			vm->bg = (uint16_t)a[0];
			vm->bg_anim = (uint16_t)a[1];
			clear_scene(vm);
			break;
		case OP_BACKGROUND:
			vm->bg = (uint16_t)a[0];
			break;
		case OP_SHOW:
			scene_show(vm, a);
			break;
		case OP_ORDER:
			scene_order(vm, a[0], a[1], a[2]);
			break;
		case OP_SHOW_RANDOM:
			scene_show_random(vm, a);
			break;
		case OP_HIDE: {
			VmSprite *s = vm_sprite(vm, a[0]);
			if (s)
				s->used = 0;
			break;
		}

		case OP_JUMP:
			vm->pc = (uint32_t)a[0];
			continue;
		case OP_JUMP_IF_FALSE:
			if (vm->sp < 1)
				return fail(vm, "pila vacia");
			if (!vm->stack[--vm->sp])
				vm->pc = (uint32_t)a[0];
			continue;
		case OP_CALL:
			if (vm->ncalls >= VM_CALLS)
				return fail(vm, "pila de CALL desbordada");
			vm->calls[vm->ncalls].chapter = vm->chapter;
			vm->calls[vm->ncalls].pc = vm->pc;
			vm->ncalls++;
			vm->pc = (uint32_t)a[0];
			continue;
		case OP_RETURN: {
			int target;
			uint32_t pc;

			if (vm->ncalls == 0)
				return VM_EV_END;
			vm->ncalls--;
			target = vm->calls[vm->ncalls].chapter;
			pc = vm->calls[vm->ncalls].pc;
			if (target != vm->chapter) {
				if (vm->host->load_chapter(vm->host->user, target, &vm->ch) != 0)
					return fail(vm, "no se pudo cargar el capitulo de retorno");
				vm->chapter = target;
			}
			vm->pc = pc;
			continue;
		}
		case OP_LOAD_CHAPTER:
			if (a[2] == 0) {
				if (vm->ncalls >= VM_CALLS)
					return fail(vm, "pila de CALL desbordada");
				vm->calls[vm->ncalls].chapter = vm->chapter;
				vm->calls[vm->ncalls].pc = vm->pc;
				vm->ncalls++;
			}
			if (vm->host->notify)
				vm->host->notify(vm->host->user, op, a, info->nfields);
			if (vm->host->load_chapter(vm->host->user, a[0], &vm->ch) != 0)
				return fail(vm, "no se pudo cargar el capitulo");
			vm->chapter = a[0];
			vm->pc = (uint32_t)a[1];
			continue;

		case OP_SET_VAR:
			vm->vars[a[0]] = (int16_t)a[1];
			continue;
		case OP_ADD_VAR:
			vm->vars[a[0]] = (int16_t)(vm->vars[a[0]] + a[1]);
			continue;
		case OP_PUSH_VAR:
			if (push(vm, vm->vars[a[0]]))
				return fail(vm, "pila de expresiones desbordada");
			continue;
		case OP_PUSH_CONST:
			if (push(vm, a[0]))
				return fail(vm, "pila de expresiones desbordada");
			continue;
		case OP_STORE_VAR:
			if (vm->sp < 1)
				return fail(vm, "pila vacia");
			vm->vars[a[0]] = vm->stack[--vm->sp];
			continue;
		case OP_OP:
			if (vm->sp < ((a[0] == 8) ? 1 : 2))
				return fail(vm, "pila vacia");
			apply_op(vm, a[0]);
			continue;
		default:
			break;
		}

		/* Instrucciones de escena y de audio ya aplicadas: solo se avisa al anfitrion */
		if (vm->host->notify)
			vm->host->notify(vm->host->user, op, a, info->nfields);
	}
}
