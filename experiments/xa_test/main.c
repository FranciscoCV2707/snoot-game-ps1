/*
 * Prueba XA + carga de datos del CD (Fase 2).
 *
 * Reproduce una pista XA (archivo de 8 canales entrelazados) y mide cuanto dura
 * la pausa de la musica al cargar archivos del CD.
 *
 * Controles:
 *   Cruz      iniciar musica (canal actual)
 *   Circulo   detener musica
 *   L1 / R1   canal anterior / siguiente (sin reiniciar)
 *   Cuadrado  cargar 1 fondo (58 KB) con pausa y reanudar la musica
 *   Triangulo cargar 4 fondos + capitulo (360 KB) con pausa y reanudar
 *   L2        cargar 1 fondo SIN pausar (la musica probablemente se corta)
 */

#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <psxetc.h>
#include <psxgte.h>
#include <psxgpu.h>
#include <psxapi.h>
#include <psxpad.h>
#include <psxspu.h>
#include <psxcd.h>

#define SCREEN_XRES 320
#define SCREEN_YRES 240
#define NUM_CHANNELS 16      /* 37.8 kHz mono a 2x: 16 carriles entrelazados */
#define SECTORS_PER_SLOT 16
#define LOAD_BUF_BYTES (400 * 1024)

static DISPENV disp[2];
static DRAWENV draw[2];
static int db = 0;
static char padbuff[2][34];
static uint32_t load_buf[LOAD_BUF_BYTES / 4];

typedef struct {
	uint8_t file, channel, submode, coding_info;
} XaHeader;

typedef struct {
	CdlLOC pos;
	XaHeader xa_header[2];
	uint8_t data[2048];
	uint32_t edc;
	uint8_t ecc[276];
} Sector;

static Sector sector;
static CdlLOC xa_loc;
static int xa_start_lba;
static int xa_total_sectors;
static volatile int num_loops = 0;

static int channel = 0;
static int music_playing = 0;
static int music_base_pos = 0;     /* sector offset dentro del archivo al iniciar/reanudar */
static int music_start_frame = 0;  /* VSync al iniciar/reanudar */

static int last_pause_ms, last_load_ms, last_seek_ms, last_gap_ms, last_bytes, last_kbs;
static const char *last_test = "(ninguna)";

static int frames_to_ms(int frames) { return frames * 1000 / 60; }

static void cd_event_handler(CdlIntrResult event, uint8_t *payload)
{
	if (event != CdlDataReady)
		return;

	CdGetSector(&sector, sizeof(Sector) / 4);

	/* Si llega un sector que no es audio, el archivo termino: volver al inicio */
	if (!(sector.xa_header[0].submode & 4) && !(sector.xa_header[1].submode & 4)) {
		CdControlF(CdlReadS, &xa_loc);
		num_loops++;
		music_base_pos = 0;
		music_start_frame = VSync(-1);
	}
}

static void init(void)
{
	ResetGraph(0);
	SpuInit();
	CdInit();

	SetDefDispEnv(&disp[0], 0, 0, SCREEN_XRES, SCREEN_YRES);
	SetDefDispEnv(&disp[1], 0, SCREEN_YRES, SCREEN_XRES, SCREEN_YRES);
	SetDefDrawEnv(&draw[0], 0, SCREEN_YRES, SCREEN_XRES, SCREEN_YRES);
	SetDefDrawEnv(&draw[1], 0, 0, SCREEN_XRES, SCREEN_YRES);
	setRGB0(&draw[0], 20, 20, 40);
	draw[0].isbg = 1;
	setRGB0(&draw[1], 20, 20, 40);
	draw[1].isbg = 1;

	FntLoad(960, 0);
	FntOpen(8, 8, 304, 224, 0, 512);

	InitPAD(padbuff[0], 34, padbuff[1], 34);
	StartPAD();
	ChangeClearPAD(0);
}

static void start_xa(int sector_offset)
{
	CdlLOC loc;
	CdlFILTER filter;
	int mode = CdlModeSpeed | CdlModeRT | CdlModeSF;

	if (sector_offset >= xa_total_sectors)
		sector_offset = 0;
	sector_offset -= sector_offset % SECTORS_PER_SLOT;

	CdIntToPos(xa_start_lba + sector_offset, &loc);
	CdControl(CdlSetmode, &mode, 0);
	filter.file = 1;
	filter.chan = channel;
	CdControl(CdlSetfilter, &filter, 0);
	CdControl(CdlReadS, &loc, 0);

	music_base_pos = sector_offset;
	music_start_frame = VSync(-1);
	music_playing = 1;
}

static int music_position(void)
{
	/* 150 sectores por segundo a 2x, 60 cuadros por segundo: 2.5 sectores por cuadro */
	return music_base_pos + ((VSync(-1) - music_start_frame) * 5) / 2;
}

static int load_file(const char *name, uint32_t *dst, int max_bytes)
{
	CdlFILE file;
	int sectors;

	if (!CdSearchFile(&file, name))
		return 0;
	sectors = (file.size + 2047) / 2048;
	if (sectors * 2048 > max_bytes)
		return 0;
	CdControl(CdlSetloc, &file.pos, 0);
	CdRead(sectors, dst, CdlModeSpeed);
	CdReadSync(0, 0);
	return sectors * 2048;
}

static void run_load_test(const char *label, int num_bg, int with_chapter, int pause_music)
{
	static const char *names[] = { "\\BG0.BIN", "\\BG1.BIN", "\\BG2.BIN", "\\BG3.BIN" };
	int was_playing = music_playing && pause_music;
	int resume_pos = 0;
	int t_start = VSync(-1), t_pause, t_load0, t_load1, t_seek1, t_end;
	int bytes = 0, offset = 0, i, n;
	CdlLOC loc;

	if (was_playing) {
		resume_pos = music_position();
		CdControlB(CdlPause, 0, 0);
	}
	t_pause = VSync(-1);

	t_load0 = VSync(-1);
	for (i = 0; i < num_bg; i++) {
		n = load_file(names[i], load_buf + offset / 4, LOAD_BUF_BYTES - offset);
		offset += n;
		bytes += n;
	}
	if (with_chapter) {
		n = load_file("\\CHAP.BIN", load_buf + offset / 4, LOAD_BUF_BYTES - offset);
		bytes += n;
	}
	t_load1 = VSync(-1);

	t_seek1 = t_load1;
	if (was_playing) {
		start_xa(resume_pos % xa_total_sectors);
		t_seek1 = VSync(-1);
	} else if (pause_music == 0) {
		/* sin pausa: no se reanuda; el estado de la musica se ve en pantalla */
		music_playing = 0;
	}
	t_end = VSync(-1);

	last_test = label;
	last_pause_ms = frames_to_ms(t_pause - t_start);
	last_load_ms = frames_to_ms(t_load1 - t_load0);
	last_seek_ms = frames_to_ms(t_seek1 - t_load1);
	last_gap_ms = frames_to_ms(t_end - t_start);
	last_bytes = bytes;
	last_kbs = last_load_ms ? (bytes / 1024) * 1000 / last_load_ms : 0;
	(void)loc;
}

int main(int argc, const char *argv[])
{
	CdlFILE file;
	PADTYPE *pad;
	int prev_btn = 0xFFFF, btn, pressed;
	int mode;
	int counter = 0;

	init();

	if (!CdSearchFile(&file, "\\MUSIC.XA")) {
		printf("MUSIC.XA no encontrado\n");
		return 0;
	}
	xa_loc = file.pos;
	xa_start_lba = CdPosToInt(&file.pos);
	xa_total_sectors = file.size / 2048;

	EnterCriticalSection();
	CdReadyCallback(&cd_event_handler);
	ExitCriticalSection();

	mode = CdlModeSpeed | CdlModeRT | CdlModeSF;
	CdControl(CdlSetmode, &mode, 0);

	while (1) {
		pad = (PADTYPE *)padbuff[0];
		btn = 0xFFFF;
		if (pad->stat == 0 && (pad->type == 0x4 || pad->type == 0x5 || pad->type == 0x7))
			btn = pad->btn;
		pressed = (~btn) & prev_btn;  /* botones recien presionados (activos en 0) */
		prev_btn = btn;

		if (pressed & PAD_CROSS)
			start_xa(0);
		if (pressed & PAD_CIRCLE) {
			CdControl(CdlPause, 0, 0);
			music_playing = 0;
		}
		if (pressed & (PAD_L1 | PAD_R1)) {
			CdlFILTER filter;
			channel = (channel + ((pressed & PAD_R1) ? 1 : NUM_CHANNELS - 1)) % NUM_CHANNELS;
			filter.file = 1;
			filter.chan = channel;
			CdControl(CdlSetfilter, &filter, 0);
		}
		if (pressed & PAD_SQUARE)
			run_load_test("1 fondo, con pausa", 1, 0, 1);
		if (pressed & PAD_TRIANGLE)
			run_load_test("4 fondos + capitulo, con pausa", 4, 1, 1);
		if (pressed & PAD_L2)
			run_load_test("1 fondo, SIN pausa", 1, 0, 0);

		FntPrint(-1, "PRUEBA XA + CARGA DE CD\n\n");
		FntPrint(-1, "Canal: %d   Musica: %s   Vueltas: %d\n", channel, music_playing ? "SI" : "no", num_loops);
		FntPrint(-1, "Posicion: %d / %d sectores\n", music_playing ? music_position() % xa_total_sectors : 0, xa_total_sectors);
		FntPrint(-1, "CdStatus: %02x\n\n", CdStatus());
		FntPrint(-1, "Ultima prueba: %s\n", last_test);
		FntPrint(-1, " Pausar CD:  %d ms\n", last_pause_ms);
		FntPrint(-1, " Carga:      %d ms (%d KB, %d KB/s)\n", last_load_ms, last_bytes / 1024, last_kbs);
		FntPrint(-1, " Reanudar:   %d ms\n", last_seek_ms);
		FntPrint(-1, " HUECO TOTAL DE MUSICA: %d ms\n\n", last_gap_ms);
		FntPrint(-1, "X iniciar  O detener  L1/R1 canal\n");
		FntPrint(-1, "[] 1 fondo  /\\ 4 fondos+cap  L2 sin pausa\n");

		DrawSync(0);
		VSync(0);
		PutDispEnv(&disp[db]);
		PutDrawEnv(&draw[db]);
		SetDispMask(1);
		FntFlush(-1);
		db = !db;

		counter++;
		if ((counter % 60) == 59)
			CdControl(CdlNop, 0, 0);
	}

	return 0;
}
