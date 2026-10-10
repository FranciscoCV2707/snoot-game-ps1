#include "scene.h"

static const int16_t *pos_x, *pos_y;
static int pos_count;

static uint16_t rd16(const uint8_t *p)
{
	return (uint16_t)(p[0] | (p[1] << 8));
}

static uint32_t rd32(const uint8_t *p)
{
	return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
}

void scene_set_positions(const int16_t *x, const int16_t *y, int count)
{
	pos_x = x;
	pos_y = y;
	pos_count = count;
}

const uint8_t *scene_anim(const Vm *vm, int anim)
{
	if (anim <= 0 || anim > vm->ch.anim_count || !vm->ch.anims)
		return 0;
	return vm->ch.anims + rd32(vm->ch.anims + 4 * (anim - 1));
}

static int sprite_before(const VmSprite *a, const VmSprite *b)
{
	return a->z != b->z ? a->z < b->z : a->born < b->born;
}

int scene_sorted(const Vm *vm, const VmSprite **order)
{
	int n = 0, i, j;

	for (i = 0; i < VM_MAX_SPRITES; i++)
		if (vm->sprites[i].used && vm->sprites[i].image) {
			for (j = n; j > 0 && sprite_before(&vm->sprites[i], order[j - 1]); j--)
				order[j] = order[j - 1];
			order[j] = &vm->sprites[i];
			n++;
		}
	return n;
}

/* Curvas de la tabla ANIM sobre u en 0..256: 0 lineal, 1 aceleracion, 2 desaceleracion, 3 ambas (cubicas) */
static int ease(int curve, int u)
{
	int v = 256 - u;

	switch (curve) {
	case 1:
		return (u * u * u) >> 16;
	case 2:
		return 256 - ((v * v * v) >> 16);
	case 3:
		return u < 128 ? (u * u * u) >> 14 : 256 - ((v * v * v) >> 14);
	}
	return u;
}

static int lerp(int a, int b, int u)
{
	return a + (b - a) * u / 256;
}

void scene_look(const Vm *vm, const VmSprite *s, int t, SpriteLook *out)
{
	const uint8_t *anim = scene_anim(vm, s->anim);

	out->image = s->image;
	out->flip = s->flags & 1;
	out->xa = 128;                 /* posicion por defecto de Ren'Py: centrado y apoyado abajo */
	out->ya = 256;
	out->alpha = 255;
	out->zoom = 64;
	out->r = out->g = out->b = 128;
	if (s->flags & VM_SPRITE_RANDOM) {
		/* randPosition: alfa 0 -> 1 en 0.6 s y 1 -> 0 en 1 s */
		out->xa = s->rx;
		out->ya = s->ry;
		if (t < 0 || t >= 96)
			out->alpha = 0;
		else
			out->alpha = t < 36 ? t * 255 / 36 : (96 - t) * 255 / 60;
		return;
	}
	if (anim && anim[0]) {
		int n = anim[0], loop = anim[1] & 1, events = anim[2], end = rd16(anim + 3 + 15 * (n - 1)), i;
		const uint8_t *k0, *k1, *ev = anim + 3 + 15 * n;

		if (t < 0)
			t = loop ? 0 : end;
		else if (loop && end > 0)
			t %= end;
		for (i = 0; i < n - 1 && t >= rd16(anim + 3 + 15 * (i + 1)); i++)
			;
		k0 = anim + 3 + 15 * i;
		out->xa = (int16_t)rd16(k0 + 2);
		out->ya = (int16_t)rd16(k0 + 4);
		out->alpha = k0[6];
		out->zoom = k0[8] ? k0[8] : 64;
		out->r = k0[11];
		out->g = k0[12];
		out->b = k0[13];
		if (i < n - 1) {
			int t0 = rd16(k0), t1;

			k1 = k0 + 15;
			t1 = rd16(k1);
			if (t1 > t0 && t > t0) {
				int u = ease(k1[7], (t - t0) * 256 / (t1 - t0));

				out->xa = lerp(out->xa, (int16_t)rd16(k1 + 2), u);
				out->ya = lerp(out->ya, (int16_t)rd16(k1 + 4), u);
				out->alpha = lerp(out->alpha, k1[6], u);
				out->zoom = lerp(out->zoom, k1[8] ? k1[8] : 64, u);
				out->r = lerp(out->r, k1[11], u);
				out->g = lerp(out->g, k1[12], u);
				out->b = lerp(out->b, k1[13], u);
			}
		}
		for (i = 0; i < events; i++, ev += 7)
			if (!(ev[4] & 2) && rd16(ev) <= t) {
				out->image = rd16(ev + 2);
				out->flip = ev[4] & 1;
			}
	}
	if (s->pos < pos_count) {
		out->xa = pos_x[s->pos];
		out->ya = pos_y[s->pos];
	}
}

int scene_event_images(const Vm *vm, const VmSprite *s, uint16_t *out, int max)
{
	const uint8_t *anim = scene_anim(vm, s->anim), *ev;
	int i, n = 0;

	if (!anim || !anim[0])
		return 0;
	ev = anim + 3 + 15 * anim[0];
	for (i = 0; i < anim[2] && n < max; i++, ev += 7)
		if (!(ev[4] & 2))
			out[n++] = rd16(ev + 2);
	return n;
}

void scene_solid_blend(const uint8_t *rgba, int alpha, SolidBlend *out)
{
	int a = rgba[3] * alpha / 255;
	int dark = rgba[0] < 48 && rgba[1] < 48 && rgba[2] < 48;

	out->r = rgba[0];
	out->g = rgba[1];
	out->b = rgba[2];
	out->passes = 1;
	if (a < 20) {
		out->mode = 0;
		out->passes = 0;
	} else if (a >= 230) {
		out->mode = 0;
	} else if (a < 90) {
		if (dark) {
			/* oscurecer poco: restar un gris (fondo - a/2), cercano a fondo * (1 - a) en tonos medios */
			out->mode = 3;
			out->r = out->g = out->b = a / 2;
		} else {
			out->mode = 4;          /* fondo + color/4, con el color escalado al alfa */
			out->r = rgba[0] * a * 4 / 255 > 255 ? 255 : rgba[0] * a * 4 / 255;
			out->g = rgba[1] * a * 4 / 255 > 255 ? 255 : rgba[1] * a * 4 / 255;
			out->b = rgba[2] * a * 4 / 255 > 255 ? 255 : rgba[2] * a * 4 / 255;
		}
	} else if (a < 166) {
		out->mode = 1;              /* 50% */
	} else {
		out->mode = 1;              /* 75%: dos pasadas al 50% */
		out->passes = 2;
	}
}
