/* The frame time log of d3d8_gl.c (frame_log_present and the rest), taken from
the source by tools/test_frame_log.py, against a clock the test sets. */
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

typedef int BOOL;
#define TRUE 1
#define FALSE 0
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "line %d: %s\n", __LINE__, #x); exit(1); } } while (0)

static long long fake_now = 5000000000LL;

static int fake_clock_gettime(int id, struct timespec *now)
{
	(void)id;
	now->tv_sec = (time_t)(fake_now / 1000000000LL);
	now->tv_nsec = (long)(fake_now % 1000000000LL);
	return 0;
}
#define clock_gettime(id, now) fake_clock_gettime(id, now)

static struct
{
	BOOL frame_log;
} debug_settings;

static char lines[512][400];
static int line_count;

static void platform_log(const char *format, ...)
{
	va_list arguments;

	va_start(arguments, format);
	if (line_count < 512)
		vsnprintf(lines[line_count], sizeof(lines[0]), format, arguments);
	line_count++;
	va_end(arguments);
}

#include "frame_log.inc"

static unsigned long frame_number;

/* one frame: the game's work, the swap, what follows it, in microseconds */
static void frame(long long game, long long swap, long long after)
{
	fake_now += game * 1000;
	frame_log_swap_begin();
	fake_now += swap * 1000;
	frame_log_swap_end();
	fake_now += after * 1000;
	frame_log_present(++frame_number);
}

static int count_containing(const char *text)
{
	int index, found = 0;

	for (index = 0; index < line_count && index < 512; index++)
	{
		if (strstr(lines[index], text))
			found++;
	}
	return found;
}

int main(int argc, char **argv)
{
	int index;

	if (argc != 2)
		return 2;
	debug_settings.frame_log = TRUE;
	if (!strcmp(argv[1], "steady"))
	{
		/* (120 frames a second: nothing to report until the 10 seconds are up) */
		for (index = 0; index < 1000; index++)
			frame(3000, 4000, 1333);
		CHECK(line_count == 0);
		for (index = 0; index < 300; index++)
			frame(3000, 4000, 1333);
		CHECK(line_count == 1 && strstr(lines[0], "summary") && strstr(lines[0], "0 hitches"));
		CHECK(strstr(lines[0], "(120 fps)") != NULL);
		return 0;
	}
	if (!strcmp(argv[1], "hitch"))
	{
		for (index = 0; index < 100; index++)
			frame(3000, 4000, 1333);
		frame(3000, 20000, 2000);
		CHECK(line_count == 1);
		CHECK(strstr(lines[0], "interval=25.000 ms (game 3.000, swap 20.000, after 2.000)"));
		CHECK(strstr(lines[0], "t=") && strstr(lines[0], "frame=101"));
		/* (the frames after it, steady again, are not hitches) */
		for (index = 0; index < 100; index++)
			frame(3000, 4000, 1333);
		CHECK(line_count == 1);
		return 0;
	}
	if (!strcmp(argv[1], "rate_limit"))
	{
		for (index = 0; index < 100; index++)
			frame(500, 400, 100);
		/* (a slow frame after each fast one: seventy of them in under a second) */
		for (index = 0; index < 70; index++)
		{
			frame(500, 400, 100);
			frame(10000, 1500, 500);
		}
		CHECK(count_containing("interval=") <= 30 && count_containing("interval=") >= 20);
		return 0;
	}
	if (!strcmp(argv[1], "disabled"))
	{
		debug_settings.frame_log = FALSE;
		for (index = 0; index < 100; index++)
			frame(3000, 4000, 1333);
		frame(3000, 40000, 2000);
		for (index = 0; index < 2000; index++)
			frame(3000, 4000, 1333);
		CHECK(line_count == 0);
		return 0;
	}
	return 2;
}
