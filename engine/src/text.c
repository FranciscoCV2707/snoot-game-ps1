#include <stdio.h>
#include <psxgpu.h>
#include "text.h"
#include "video.h"

typedef struct {
	uint16_t cp;
	uint8_t style, u, v, w, h;
	int8_t xoff, yoff;
	uint8_t adv;
} Glyph;                                    /* 10 bytes, igual que FONT.BIN */

static const Glyph *glyphs;
static int glyph_count;
static int line_h = 14;
static int ascent = 11;

static uint16_t rd16(const uint8_t *p)
{
	return (uint16_t)(p[0] | (p[1] << 8));
}

int font_load(const uint8_t *file, int size)
{
	RECT rect;
	int table_end, atlas_off;
	static Glyph table[512];
	int i;

	if (size < 12 || file[0] != 'F' || file[1] != 'N' || file[2] != 'T' || file[3] != '1')
		return -1;
	line_h = file[4];
	ascent = file[5];
	glyph_count = rd16(file + 6);
	if (glyph_count > 512)
		return -1;
	/* La tabla del archivo no esta alineada a 2 bytes en el struct de C: se copia campo por campo */
	for (i = 0; i < glyph_count; i++) {
		const uint8_t *g = file + 8 + i * 10;
		table[i].cp = rd16(g);
		table[i].style = g[2];
		table[i].u = g[3];
		table[i].v = g[4];
		table[i].w = g[5];
		table[i].h = g[6];
		table[i].xoff = (int8_t)g[7];
		table[i].yoff = (int8_t)g[8];
		table[i].adv = g[9];
	}
	glyphs = table;
	table_end = 8 + glyph_count * 10;
	atlas_off = (table_end + 3) & ~3;

	/* Atlas de 256x256 a 4 bits = 64 palabras de ancho */
	setRECT(&rect, VRAM_FONT_X, VRAM_FONT_Y, 64, 256);
	LoadImage(&rect, (const uint32_t *)(file + atlas_off));
	DrawSync(0);

	/* 16 niveles de gris; el indice 0 es transparente */
	{
		static uint16_t clut[16] __attribute__((aligned(4)));
		for (i = 0; i < 16; i++) {
			int v = (i * 31) / 15;
			clut[i] = i ? (uint16_t)(v | (v << 5) | (v << 10)) : 0;
		}
		setRECT(&rect, CLUT_FONT_X, CLUT_FONT_Y, 16, 1);
		LoadImage(&rect, (const uint32_t *)clut);
		DrawSync(0);
	}
	return 0;
}

int font_line_height(void)
{
	return line_h;
}

static const Glyph *find_glyph(uint32_t cp, int style)
{
	int lo = 0, hi = glyph_count - 1;
	uint32_t key = cp * 2 + (style == 1 ? 1 : 0);

	while (lo <= hi) {
		int mid = (lo + hi) / 2;
		uint32_t k = glyphs[mid].cp * 2 + glyphs[mid].style;
		if (k == key)
			return &glyphs[mid];
		if (k < key)
			lo = mid + 1;
		else
			hi = mid - 1;
	}
	return (style == 1) ? find_glyph(cp, 0) : 0;
}

/* Decodifica un caracter UTF-8 y avanza el puntero */
static uint32_t utf8_next(const char **pp)
{
	const uint8_t *p = (const uint8_t *)*pp;
	uint32_t c = p[0];

	if (c < 0x80) {
		*pp += 1;
		return c;
	}
	if ((c & 0xE0) == 0xC0) {
		*pp += 2;
		return ((c & 0x1F) << 6) | (p[1] & 0x3F);
	}
	if ((c & 0xF0) == 0xE0) {
		*pp += 3;
		return ((c & 0x0F) << 12) | ((p[1] & 0x3F) << 6) | (p[2] & 0x3F);
	}
	*pp += 4;
	return ((c & 0x07) << 18) | ((p[1] & 0x3F) << 12) | ((p[2] & 0x3F) << 6) | (p[3] & 0x3F);
}

/* Agrega un glifo (el tpage de la fuente se agrega una vez por llamada de dibujo) */
static void add_glyph(int layer, int x, int y, const Glyph *g, int r, int gc, int b)
{
	SPRT *s;

	if (!g->w || !g->h)
		return;
	s = (SPRT *)video_alloc(sizeof(SPRT));
	if (!s)
		return;
	setSprt(s);
	setXY0(s, x + g->xoff, y + ascent + g->yoff);
	setWH(s, g->w, g->h);
	setUV0(s, g->u, g->v);
	setRGB0(s, r, gc, b);
	setClut(s, CLUT_FONT_X, CLUT_FONT_Y);
	setSemiTrans(s, 1);                      /* mezcla aditiva: el borde suave se funde con el fondo */
	video_add(layer, s);
}

void font_draw(int layer, int x, int y, const char *utf8, int r, int g, int b)
{
	const char *p = utf8;
	int cx = x;

	while (*p) {
		uint32_t cp = utf8_next(&p);
		const Glyph *gl;

		if (cp == '\n') {
			cx = x;
			y += line_h;
			continue;
		}
		gl = find_glyph(cp, 0);
		if (!gl)
			continue;
		add_glyph(layer, cx, y, gl, r, g, b);
		cx += gl->adv;
	}
	video_set_tpage(layer, 0, 1, VRAM_FONT_X, VRAM_FONT_Y);
}

int font_width(const char *utf8)
{
	const char *p = utf8;
	int w = 0;

	while (*p) {
		uint32_t cp = utf8_next(&p);
		const Glyph *gl;

		if (cp == '\n')
			break;
		gl = find_glyph(cp, 0);
		if (gl)
			w += gl->adv;
	}
	return w;
}

/* ---------------------------------------------------------------- maquina de escribir */
void text_start(TextRun *t, const char *utf8)
{
	t->start = t->page = t->pos = utf8;
	t->cps = TEXT_DEFAULT_CPS;
	t->acc = 0;
	t->wait = 0;
	t->style = 0;
	t->at_page_end = 0;
	t->at_end = (*utf8 == 0);
	t->auto_next = 0;
}

/* Procesa un elemento (codigo de control o caracter). Devuelve 1 si era un caracter visible. */
static int step(TextRun *t)
{
	const char *p = t->pos;
	uint32_t c;

	if (!*p) {
		t->at_end = 1;
		return 0;
	}
	c = utf8_next(&p);
	switch (c) {
	case TEXT_STYLE:
		t->style = (uint8_t)utf8_next(&p);
		t->pos = p;
		return 0;
	case TEXT_WAIT:
		t->wait = (int)utf8_next(&p) * 6;      /* decimas de segundo a cuadros */
		t->pos = p;
		return 0;
	case TEXT_SPEED: {
		int n = (int)utf8_next(&p);
		t->cps = n ? n : TEXT_DEFAULT_CPS;
		t->pos = p;
		return 0;
	}
	case TEXT_NOWAIT:
		t->auto_next = 1;
		t->pos = p;
		return 0;
	case TEXT_FAST:
		t->pos = p;
		return 0;
	case TEXT_SIZE:
		(void)utf8_next(&p);
		t->pos = p;
		return 0;
	case TEXT_PAGE:
		t->at_page_end = 1;                    /* se queda en el codigo hasta que se pida otra pagina */
		return 0;
	default:
		t->pos = p;
		return 1;
	}
}

void text_update(TextRun *t)
{
	if (t->at_end || t->at_page_end)
		return;
	if (t->wait > 0) {
		t->wait--;
		return;
	}
	t->acc += (t->cps * 256) / 60;
	while (t->acc >= 256 && !t->at_end && !t->at_page_end && t->wait == 0) {
		if (step(t))
			t->acc -= 256;
		else if (t->wait > 0)
			break;
	}
}

void text_reveal_page(TextRun *t)
{
	while (!t->at_end && !t->at_page_end)
		step(t);
	t->wait = 0;
}

int text_page_done(const TextRun *t)
{
	return t->at_page_end || t->at_end;
}

int text_finished(const TextRun *t)
{
	return t->at_end;
}

void text_next_page(TextRun *t)
{
	if (t->at_page_end) {
		const char *p = t->pos;
		utf8_next(&p);                         /* salta el codigo de pagina */
		t->pos = t->page = p;
		t->at_page_end = 0;
		t->acc = 0;
		if (!*p)
			t->at_end = 1;
	}
}

void text_draw(const TextRun *t, int layer, int x, int y, int r, int g, int b)
{
	const char *p = t->page;
	int cx = x, cy = y, style = 0;

	/* se redibuja desde el inicio de la pagina hasta lo revelado */
	while (p < t->pos && *p) {
		uint32_t c = utf8_next(&p);
		const Glyph *gl;

		if (c == TEXT_STYLE) {
			style = (int)utf8_next(&p);
			continue;
		}
		if (c == TEXT_WAIT || c == TEXT_SPEED || c == TEXT_SIZE) {
			(void)utf8_next(&p);
			continue;
		}
		if (c == TEXT_NOWAIT || c == TEXT_FAST || c == TEXT_PAGE)
			continue;
		if (c == TEXT_NEWLINE) {
			cx = x;
			cy += line_h;
			continue;
		}
		gl = find_glyph(c, style);
		if (!gl)
			continue;
		add_glyph(layer, cx, cy, gl, r, g, b);
		if (style == 2)
			add_glyph(layer, cx + 1, cy, gl, r, g, b);   /* negrita: se dibuja dos veces */
		cx += gl->adv;
	}
	video_set_tpage(layer, 0, 1, VRAM_FONT_X, VRAM_FONT_Y);
}
