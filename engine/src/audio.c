#include <stdio.h>
#include <string.h>
#include <psxapi.h>
#include <psxcd.h>
#include <psxgpu.h>
#include <psxspu.h>
#include "audio.h"
#include "cd.h"
#include "res.h"

#define MAX_AUDIO 256
#define XA_LANES 16
#define KIND_MUSIC 1
#define KIND_FAMILY_END 2
#define KIND_SFX 3
#define KIND_AMBIENT 4

/* RAM de la SPU: los primeros 4 KB son del sistema (ver el ejemplo vagsample de PSn00bSDK); 4 espacios fijos de
 * ambientes al final (cada bucle pesa ~54 KB) y en medio una zona de efectos que se vacia entera cuando se llena. */
#define SPU_BASE 0x1010
#define SPU_END 0x80000
#define AMBIENT_SLOTS 4
#define AMBIENT_BYTES (56 * 1024)
#define AMBIENT_BASE (SPU_END - AMBIENT_SLOTS * AMBIENT_BYTES)
#define SFX_FIRST_VOICE AMBIENT_SLOTS          /* voces 0-3: ambientes; 4-23: efectos */
#define SFX_VOICES 20
#define MAX_SFX_CACHED 48
#define CHUNK_SECTORS 16                       /* los efectos se suben a la SPU de a 32 KB */

#define VOL_ONE 4096                            /* volumenes internos: 4096 = 100% */

typedef struct {
	uint8_t kind, lane, copies, flags;
	uint32_t start, length, aux;
} Entry;

typedef struct {
	int cur, target, step;                      /* volumen de fundido actual y destino, paso por cuadro */
} Fade;

static Entry entries[MAX_AUDIO];
static int entry_count;
static int xa_lba;
static int music_level = 10, sfx_level = 10;
static uint8_t chunk[CHUNK_SECTORS * 2048] __attribute__((aligned(4)));

/* musica */
static int cur = -1, queued = -1, playing, lane;
static int base_sector, start_frame;           /* sector del archivo donde empezo la lectura y cuadro de ese momento */
static int track_start, track_end, track_loop; /* rango de la pista en el archivo (sectores) */
static int end_id = -1, end_at = -1;           /* final de familia pendiente: cambia de carril al llegar al sector */
static int stop_when_silent, cd_depth, batch_depth, resume_sector = -1;
static Fade music_fade, music_script;

/* efectos y ambientes */
typedef struct {
	int id, addr, bytes, ready;                 /* ready = 0: se esta subiendo en segundo plano */
} Cached;

static Cached sfx_cache[MAX_SFX_CACHED];
static int sfx_cached, sfx_next = SPU_BASE, next_voice;
static int ambient_id[AMBIENT_SLOTS] = { -1, -1, -1, -1 };
static Fade ambient_fade[AMBIENT_SLOTS], ambient_script[AMBIENT_SLOTS], sfx_script;
static int ambient_stop[AMBIENT_SLOTS];

static uint16_t rd16(const uint8_t *p)
{
	return (uint16_t)(p[0] | (p[1] << 8));
}

static uint32_t rd32(const uint8_t *p)
{
	return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void fade_set(Fade *f, int target, int tenths)
{
	int frames = tenths * 6;

	f->target = target;
	f->step = frames > 0 ? (target > f->cur ? target - f->cur : f->cur - target) / frames + 1 : VOL_ONE;
}

static int fade_tick(Fade *f)
{
	if (f->cur < f->target)
		f->cur = f->cur + f->step > f->target ? f->target : f->cur + f->step;
	else if (f->cur > f->target)
		f->cur = f->cur - f->step < f->target ? f->target : f->cur - f->step;
	return f->cur;
}

int audio_init(void)
{
	static uint8_t buf[MAX_AUDIO * 20 + 2048] __attribute__((aligned(4)));
	int size, i, xa_size;

	SpuInit();
	music_script.cur = music_script.target = VOL_ONE;
	sfx_script.cur = sfx_script.target = VOL_ONE;
	for (i = 0; i < AMBIENT_SLOTS; i++)
		ambient_script[i].cur = ambient_script[i].target = VOL_ONE;
	SpuSetCommonCDVolume(0, 0);

	size = cd_read_file("\\DATA\\AUDIO.BIN", buf, sizeof(buf));
	if (size < 6 || memcmp(buf, "AIX1", 4) != 0) {
		printf("audio: sin indice\n");
		return -1;
	}
	entry_count = rd16(buf + 4);
	if (entry_count > MAX_AUDIO)
		entry_count = MAX_AUDIO;
	for (i = 0; i < entry_count; i++) {
		const uint8_t *p = buf + 6 + 20 * i;

		entries[i].kind = p[0];
		entries[i].lane = p[1];
		entries[i].copies = p[2];
		entries[i].flags = p[3];
		entries[i].start = rd32(p + 4);
		entries[i].length = rd32(p + 8);
		entries[i].aux = rd32(p + 12);
	}
	if (cd_find("\\MUSIC.XA", &xa_lba, &xa_size) != 0)
		xa_lba = -1;
	return 0;
}

/* ---------------------------------------------------------------- musica */
static int music_position(void)
{
	/* 2x: 150 sectores por segundo, 2.5 por cuadro */
	return base_sector + ((VSync(-1) - start_frame) * 5) / 2;
}

static void set_lane(int new_lane)
{
	CdlFILTER filter;

	cd_wait();                           /* no interrumpir una precarga en curso */
	filter.file = 1;
	filter.chan = (uint8_t)new_lane;
	CdControl(CdlSetfilter, &filter, 0);
	lane = new_lane;
}

static void start_read(int sector)
{
	CdlLOC loc;
	int mode = CdlModeSpeed | CdlModeRT | CdlModeSF;

	sector -= ((sector - lane) % XA_LANES + XA_LANES) % XA_LANES;   /* primer sector del carril en esa ranura */
	cd_wait();
	CdIntToPos(xa_lba + sector, &loc);
	CdControl(CdlSetmode, &mode, 0);
	set_lane(lane);
	CdControl(CdlReadS, &loc, 0);
	base_sector = sector;
	start_frame = VSync(-1);
	playing = 1;
}

static void apply_music_volume(void)
{
	int v = (music_fade.cur * music_script.cur / VOL_ONE) * music_level / 10;

	v = v * 0x7fff / VOL_ONE;
	SpuSetCommonCDVolume(v, v);
}

static void adopt(int id)
{
	const Entry *e = &entries[id];

	cur = id;
	lane = e->lane;
	track_start = (int)e->start;
	track_end = (int)(e->start + e->length * XA_LANES);
	track_loop = e->flags & 1;
}

void audio_music_play(int id, int fade_tenths, int flags)
{
	const Entry *e;

	if (id < 0 || id >= entry_count || xa_lba < 0)
		return;
	e = &entries[id];
	if (e->kind == KIND_FAMILY_END && playing) {
		/* el final se graba en un carril lateral alineado con el fin de cada copia del bucle: se cambia de carril
		 * al llegar al inicio del final de la copia que esta sonando */
		int pos = music_position(), k = 0;

		while (k < 8 && (int)(e->start + k * e->aux * XA_LANES) < pos)
			k++;
		end_id = id;
		end_at = (int)(e->start + k * e->aux * XA_LANES);
		queued = -1;
		return;
	}
	if (e->kind != KIND_MUSIC)
		return;
	stop_when_silent = 0;
	end_id = end_at = -1;
	queued = -1;
	if ((flags & 2) && playing && cur >= 0) {
		/* mezcla de stems sincronizada: misma posicion, otro carril */
		int offset = (resume_sector >= 0 ? resume_sector : music_position()) - track_start;

		adopt(id);
		set_lane(lane);
		if (resume_sector >= 0) {
			resume_sector = track_start + offset;
		} else {
			base_sector = track_start + offset;
			start_frame = VSync(-1);
		}
		fade_set(&music_fade, VOL_ONE, fade_tenths);
		return;
	}
	adopt(id);
	music_fade.cur = fade_tenths ? 0 : VOL_ONE;
	fade_set(&music_fade, VOL_ONE, fade_tenths);
	apply_music_volume();
	if (cd_depth) {
		/* hay una carga en curso: la cancion empieza cuando termine, en vez de cortarla recien empezada */
		resume_sector = track_start;
		playing = 1;
		return;
	}
	resume_sector = -1;                  /* una cancion nueva reemplaza a la que estaba en pausa por una lectura */
	start_read(track_start);
}

void audio_music_queue(int id)
{
	if (id < 0 || id >= entry_count)
		return;
	if (!playing)
		audio_music_play(id, 0, 0);
	else
		queued = id;
}

void audio_music_stop(int fade_tenths)
{
	if (!playing)
		return;
	queued = -1;
	end_id = end_at = -1;
	if (fade_tenths <= 0 || resume_sector >= 0) {     /* en pausa por una lectura: ya esta en silencio */
		cd_wait();
		CdControlB(CdlPause, 0, 0);
		playing = 0;
		cur = -1;
		resume_sector = -1;
		SpuSetCommonCDVolume(0, 0);
		return;
	}
	fade_set(&music_fade, 0, fade_tenths);
	stop_when_silent = 1;
}

static void music_update(void)
{
	int pos;

	if (!playing || cd_depth || resume_sector >= 0)
		return;
	pos = music_position();
	if (end_at >= 0 && pos >= end_at) {
		const Entry *e = &entries[end_id];

		cur = end_id;
		set_lane(e->lane);
		track_start = end_at;
		track_end = end_at + (int)e->length * XA_LANES;
		track_loop = 0;
		end_at = end_id = -1;
	}
	if (pos >= track_end) {
		if (queued >= 0 && (int)entries[queued].start == track_end && entries[queued].lane == lane) {
			adopt(queued);                       /* intro -> bucle: el bucle sigue en el mismo carril, sin buscar */
			queued = -1;
		} else if (queued >= 0) {
			int next = queued;

			queued = -1;
			adopt(next);
			start_read(track_start);
		} else if (track_loop) {
			start_read(track_start);
		} else {
			CdControlB(CdlPause, 0, 0);
			playing = 0;
			cur = -1;
		}
	}
	fade_tick(&music_fade);
	fade_tick(&music_script);
	if (stop_when_silent && music_fade.cur == 0) {
		CdControlB(CdlPause, 0, 0);
		playing = 0;
		cur = -1;
		stop_when_silent = 0;
	}
	apply_music_volume();
}

void audio_cd_begin(void)
{
	if (cd_depth++ == 0 && playing && resume_sector < 0) {
		resume_sector = music_position();
		CdControlB(CdlPause, 0, 0);
	}
}

static void resume_music(void)
{
	int sector = resume_sector;

	resume_sector = -1;
	if (sector >= track_end)
		sector = track_start;
	start_read(sector);
}

void audio_cd_end(void)
{
	if (--cd_depth == 0 && batch_depth == 0 && resume_sector >= 0)
		resume_music();
}

void audio_batch_begin(void)
{
	batch_depth++;
}

void audio_batch_end(void)
{
	if (--batch_depth == 0 && cd_depth == 0 && resume_sector >= 0)
		resume_music();
}

int audio_cd_paused(void)
{
	return resume_sector >= 0 || !playing;
}

/* ---------------------------------------------------------------- efectos */
volatile uint32_t audio_cd_uploads, audio_cd_bytes;   /* efectos y ambientes leidos del CD (prueba en emulador) */
extern volatile uint32_t res_cd_reads, res_sync_log[16], res_trace_tag;

static int upload(int id, int addr)
{
	char path[24];
	int lba, size, done = 0;

	const uint8_t *cached = res_cached_file(RES_SOUND | id, &size);

	if (cached) {                            /* ya traido a RAM por la precarga: sin tocar el CD */
		SpuSetTransferMode(SPU_TRANSFER_BY_DMA);
		SpuSetTransferStartAddr(addr);
		SpuWrite((const uint32_t *)cached, (size + 63) & ~63);
		SpuIsTransferCompleted(SPU_TRANSFER_WAIT);
		return size;
	}
	sprintf(path, "\\DATA\\S%03d.SPU", id);
	if (cd_find(path, &lba, &size) != 0)
		return -1;
	res_sync_log[res_cd_reads++ & 15] = RES_SOUND | id | res_trace_tag;
	audio_cd_uploads++;
	audio_cd_bytes += size;
	SpuSetTransferMode(SPU_TRANSFER_BY_DMA);
	while (done < size) {
		int sectors = (size - done + 2047) / 2048, bytes;

		if (sectors > CHUNK_SECTORS)
			sectors = CHUNK_SECTORS;
		if (cd_read_sectors(lba + done / 2048, sectors, chunk) != 0)
			return -1;
		bytes = sectors * 2048;
		if (bytes > size - done)
			bytes = size - done;
		SpuSetTransferStartAddr(addr + done);
		SpuWrite((const uint32_t *)chunk, (bytes + 63) & ~63);
		SpuIsTransferCompleted(SPU_TRANSFER_WAIT);
		done += bytes;
	}
	return size;
}

/* ---------------------------------------------------------------- efectos precargados en segundo plano
 * audio_preload solo los pone en cola; audio_update los sube de a 32 KB con lecturas en segundo plano mientras la
 * musica sigue en pausa (la cola la mantiene pausada). Si un efecto hace falta antes, se termina de subir al momento. */
#define BG_QUEUE 16

static uint8_t bg_chunk[CHUNK_SECTORS * 2048] __attribute__((aligned(4)));
static int bg_queue[BG_QUEUE], bg_queued, bg_hold;
static int bg_slot = -1, bg_lba, bg_size, bg_done, bg_reading;   /* subida en curso: lugar en sfx_cache */

static void bg_finish(void);

/* Reserva lugar en la zona de efectos; devuelve el indice en sfx_cache o -1 */
static int sfx_alloc(int id)
{
	int bytes = ((int)entries[id].length + 63) & ~63;

	if (bytes > AMBIENT_BASE - SPU_BASE)
		return -1;
	if (sfx_next + bytes > AMBIENT_BASE || sfx_cached == MAX_SFX_CACHED) {
		bg_finish();                             /* no pisar una subida en curso */
		sfx_cached = 0;                          /* zona llena: se vacia entera (lo que suena ya termino casi siempre) */
		sfx_next = SPU_BASE;
	}
	sfx_cache[sfx_cached].id = id;
	sfx_cache[sfx_cached].addr = sfx_next;
	sfx_cache[sfx_cached].bytes = bytes;
	sfx_cache[sfx_cached].ready = 0;
	sfx_next += bytes;
	return sfx_cached++;
}

/* Termino la lectura del pedazo en curso: se pasa a la SPU */
static void bg_chunk_done(int result)
{
	int bytes;

	bg_reading = 0;
	if (result < 0) {
		sfx_cache[bg_slot].id = -1;
		bg_slot = -1;
		return;
	}
	bytes = bg_size - bg_done < CHUNK_SECTORS * 2048 ? bg_size - bg_done : CHUNK_SECTORS * 2048;
	SpuSetTransferMode(SPU_TRANSFER_BY_DMA);
	SpuSetTransferStartAddr(sfx_cache[bg_slot].addr + bg_done);
	SpuWrite((const uint32_t *)bg_chunk, (bytes + 63) & ~63);
	SpuIsTransferCompleted(SPU_TRANSFER_WAIT);
	bg_done += bytes;
	if (bg_done >= bg_size) {
		sfx_cache[bg_slot].ready = 1;
		bg_slot = -1;
	}
}

static int bg_read_chunk(void)
{
	int sectors = (bg_size - bg_done + 2047) / 2048;

	if (sectors > CHUNK_SECTORS)
		sectors = CHUNK_SECTORS;
	if (cd_read_start(CD_OWNER_AUDIO, bg_lba + bg_done / 2048, sectors, bg_chunk) != 0) {
		bg_chunk_done(-1);
		return -1;
	}
	audio_cd_uploads += bg_done == 0;
	audio_cd_bytes += bg_done == 0 ? bg_size : 0;
	bg_reading = 1;
	return 0;
}

/* Termina ya (esperando al CD) la subida en curso */
static void bg_finish(void)
{
	while (bg_slot >= 0) {
		if (bg_reading) {
			cd_wait();
			bg_chunk_done(cd_read_poll(CD_OWNER_AUDIO));
		} else if (bg_read_chunk() != 0) {
			return;
		}
	}
}

static void bg_release(void)
{
	bg_queued = 0;
	if (bg_hold) {
		bg_hold = 0;
		audio_cd_end();
	}
}

static void bg_update(void)
{
	char path[24];
	int r, id, i;

	if (bg_reading) {
		r = cd_read_poll(CD_OWNER_AUDIO);
		if (r > 0)
			return;
		bg_chunk_done(r);
	}
	if (bg_slot < 0) {
		/* si mientras tanto empezo otra cancion, no se le vuelve a cortar */
		if (!bg_queued || !audio_cd_paused()) {
			bg_release();
			return;
		}
		id = bg_queue[0];
		for (i = 1; i < bg_queued; i++)
			bg_queue[i - 1] = bg_queue[i];
		bg_queued--;
		sprintf(path, "\\DATA\\S%03d.SPU", id);
		if (cd_find(path, &bg_lba, &bg_size) != 0 || (bg_slot = sfx_alloc(id)) < 0)
			return;
		bg_done = 0;
	}
	if (!cd_busy())
		bg_read_chunk();
}

static int sfx_addr(int id)
{
	int i;

	for (i = 0; i < sfx_cached; i++)
		if (sfx_cache[i].id == id) {
			if (!sfx_cache[i].ready)
				bg_finish();
			return sfx_cache[i].addr;
		}
	for (i = 0; i < bg_queued; i++)          /* estaba en cola: se sube ya */
		if (bg_queue[i] == id) {
			bg_queue[i] = bg_queue[--bg_queued];
			break;
		}
	i = sfx_alloc(id);
	if (i < 0)
		return -1;
	if (upload(id, sfx_cache[i].addr) < 0) {
		sfx_cache[i].id = -1;
		return -1;
	}
	sfx_cache[i].ready = 1;
	return sfx_cache[i].addr;
}

int audio_loading(void)
{
	return bg_hold;
}

int audio_sfx_missing(int id)
{
	int i;

	if (id < 0 || id >= entry_count || entries[id].kind != KIND_SFX)
		return 0;
	for (i = 0; i < sfx_cached; i++)
		if (sfx_cache[i].id == id)
			return 0;
	for (i = 0; i < bg_queued; i++)
		if (bg_queue[i] == id)
			return 0;
	return 1;
}

int audio_ambient_missing(int slot, int id)
{
	if (slot < 0 || slot >= AMBIENT_SLOTS || id < 0 || id >= entry_count || entries[id].kind == KIND_MUSIC ||
	    (int)entries[id].length > AMBIENT_BYTES)
		return 0;
	return ambient_id[slot] != id;
}

void audio_preload(int id)
{
	int i;

	if (id < 0 || id >= entry_count || entries[id].kind != KIND_SFX || bg_queued == BG_QUEUE)
		return;
	for (i = 0; i < sfx_cached; i++)
		if (sfx_cache[i].id == id)
			return;
	for (i = 0; i < bg_queued; i++)
		if (bg_queue[i] == id)
			return;
	bg_queue[bg_queued++] = id;
	if (!bg_hold) {
		bg_hold = 1;
		audio_cd_begin();                    /* la musica sigue en pausa hasta vaciar la cola */
	}
}

static void voice_start(int voice, int addr, int rate, int vol)
{
	SpuSetKey(0, 1 << voice);
	SPU_CH_FREQ(voice) = getSPUSampleRate(rate);
	SPU_CH_ADDR(voice) = getSPUAddr(addr);
	SPU_CH_VOL_L(voice) = (uint16_t)vol;
	SPU_CH_VOL_R(voice) = (uint16_t)vol;
	SPU_CH_ADSR1(voice) = 0x00ff;
	SPU_CH_ADSR2(voice) = 0x0000;
	SpuSetKey(1, 1 << voice);
}

static int sfx_volume(void)
{
	return (sfx_script.cur * sfx_level / 10) * 0x3fff / VOL_ONE;
}

void audio_sfx_play(int id)
{
	int addr;

	if (id < 0 || id >= entry_count || entries[id].kind == KIND_MUSIC)
		return;
	addr = sfx_addr(id);
	if (addr < 0)
		return;
	voice_start(SFX_FIRST_VOICE + next_voice, addr, (int)entries[id].aux, sfx_volume());
	next_voice = (next_voice + 1) % SFX_VOICES;
}

void audio_sfx_stop(void)
{
	SpuSetKey(0, ((1 << SFX_VOICES) - 1) << SFX_FIRST_VOICE);
}

/* ---------------------------------------------------------------- ambientes */
static int ambient_volume(int slot)
{
	return ((ambient_fade[slot].cur * ambient_script[slot].cur / VOL_ONE) * sfx_level / 10) * 0x3fff / VOL_ONE;
}

void audio_ambient_play(int slot, int id, int fade_tenths)
{
	int addr = AMBIENT_BASE + slot * AMBIENT_BYTES;

	if (slot < 0 || slot >= AMBIENT_SLOTS || id < 0 || id >= entry_count || entries[id].kind == KIND_MUSIC)
		return;
	if ((int)entries[id].length > AMBIENT_BYTES)
		return;
	if (ambient_id[slot] != id) {
		SpuSetKey(0, 1 << slot);
		if (upload(id, addr) < 0)
			return;
		ambient_id[slot] = id;
	}
	ambient_stop[slot] = 0;
	ambient_fade[slot].cur = fade_tenths ? 0 : VOL_ONE;
	fade_set(&ambient_fade[slot], VOL_ONE, fade_tenths);
	voice_start(slot, addr, (int)entries[id].aux, ambient_volume(slot));
}

void audio_ambient_stop(int slot, int fade_tenths)
{
	if (slot < 0 || slot >= AMBIENT_SLOTS)
		return;
	if (fade_tenths <= 0) {
		SpuSetKey(0, 1 << slot);
		ambient_fade[slot].cur = ambient_fade[slot].target = 0;
		return;
	}
	fade_set(&ambient_fade[slot], 0, fade_tenths);
	ambient_stop[slot] = 1;
}

/* ---------------------------------------------------------------- comun */
void audio_volume(int channel, int volume, int time_tenths)
{
	int target = volume * VOL_ONE / 255;

	if (channel == AUDIO_CH_MUSIC)
		fade_set(&music_script, target, time_tenths);
	else if (channel == AUDIO_CH_SFX)
		fade_set(&sfx_script, target, time_tenths);
	else if (channel >= 1 && channel <= AMBIENT_SLOTS)
		fade_set(&ambient_script[channel - 1], target, time_tenths);
}

int audio_music_current(void)
{
	return playing && !stop_when_silent ? cur : -1;
}

int audio_ambient_current(int slot)
{
	return ambient_fade[slot].target > 0 ? ambient_id[slot] : -1;
}

void audio_set_levels(int music, int sfx)
{
	music_level = music;
	sfx_level = sfx;
}

void audio_stop_all(void)
{
	int i;

	audio_music_stop(0);
	audio_sfx_stop();
	for (i = 0; i < AMBIENT_SLOTS; i++)
		audio_ambient_stop(i, 0);
}

void audio_update(void)
{
	int i;

	music_update();
	bg_update();
	fade_tick(&sfx_script);
	for (i = 0; i < AMBIENT_SLOTS; i++) {
		fade_tick(&ambient_fade[i]);
		fade_tick(&ambient_script[i]);
		if (ambient_stop[i] && ambient_fade[i].cur == 0) {
			SpuSetKey(0, 1 << i);
			ambient_stop[i] = 0;
		}
		SPU_CH_VOL_L(i) = (uint16_t)ambient_volume(i);
		SPU_CH_VOL_R(i) = (uint16_t)ambient_volume(i);
	}
}
