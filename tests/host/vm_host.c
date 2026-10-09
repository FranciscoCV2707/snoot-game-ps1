/*
 * Arnes de PC para la VM del motor: ejecuta un camino de decisiones y escribe un registro que
 * tests/test_vm_host.py compara con el del simulador de Python.
 *
 * Uso: vm_host <build/data> <capitulo> <entrada> <decisiones separadas por coma>
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "vm.h"

static const char *data_dir;

static uint32_t rd32(const uint8_t *p)
{
	return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
}

static uint8_t *read_file(const char *path, long *size)
{
	FILE *f = fopen(path, "rb");
	uint8_t *buf;

	if (!f)
		return 0;
	fseek(f, 0, SEEK_END);
	*size = ftell(f);
	fseek(f, 0, SEEK_SET);
	buf = malloc(*size);
	if (fread(buf, 1, *size, f) != (size_t)*size) {
		fclose(f);
		return 0;
	}
	fclose(f);
	return buf;
}

static int load_chapter(void *user, int chapter, VmChapter *out)
{
	char path[512];
	long size;
	uint8_t *d;

	(void)user;
	sprintf(path, "%s/SCRIPT/C%02d.VNB", data_dir, chapter);
	d = read_file(path, &size);
	if (!d) {
		sprintf(path, "%s/SCRIPT/STORY.VNB", data_dir);
		d = read_file(path, &size);
	}
	if (!d || memcmp(d, "VNB1", 4) != 0)
		return -1;
	out->code = d + 32;
	out->code_size = rd32(d + 8);
	out->text_base = rd32(d + 12);
	out->text_count = (uint16_t)(d[16] | (d[17] << 8));
	out->anim_count = (uint16_t)(d[18] | (d[19] << 8));
	out->anims = d + rd32(d + 24);
	return 0;
}

static void print_state(Vm *vm)
{
	int tag, i, first = 1;

	printf("STATE bg=%d spr=", vm->bg);
	for (tag = 0; tag < 256; tag++) {
		VmSprite *s = vm_sprite(vm, tag);
		if (s) {
			printf("%s%d:%d", first ? "" : ",", tag, s->image);
			first = 0;
		}
	}
	printf(" vars=");
	for (i = 0; i < VM_VARS; i++)
		printf("%s%d", i ? "," : "", vm->vars[i]);
	printf("\n");
}

int main(int argc, char **argv)
{
	static const VmHost host = { 0, load_chapter, 0 };
	static Vm vm;
	const char *choices;
	int turns = 0, max_menus = argc > 5 ? atoi(argv[5]) : 200;

	if (argc < 5) {
		fprintf(stderr, "uso: vm_host dir capitulo entrada decisiones\n");
		return 2;
	}
	data_dir = argv[1];
	choices = argv[4];
	vm_init(&vm, &host);
	if (vm_start(&vm, atoi(argv[2]), (uint32_t)atol(argv[3])) != 0) {
		fprintf(stderr, "no se pudo cargar el capitulo\n");
		return 2;
	}
	for (;;) {
		VmEvent ev = vm_run(&vm);

		if (ev == VM_EV_SAY) {
			printf("SAY %d\n", vm.ev_gid);
		} else if (ev == VM_EV_MENU) {
			printf("MENU %d\n", vm.menu_n);
			print_state(&vm);
			vm.choice = 0;
			if (*choices) {
				vm.choice = atoi(choices);
				choices = strchr(choices, ',');
				choices = choices ? choices + 1 : "";
			}
			if (++turns >= max_menus) {
				printf("STOP\n");
				return 0;
			}
		} else if (ev == VM_EV_END) {
			printf("END\n");
			print_state(&vm);
			return 0;
		} else if (ev == VM_EV_ERROR) {
			printf("ERROR %s\n", vm.error);
			return 1;
		}
	}
}
