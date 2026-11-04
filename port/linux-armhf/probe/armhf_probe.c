/*
    OpenCE 32-bit ARM (armhf) feasibility probe.

    A small SDL3 and OpenGL ES program, built for AArch32 and run on a Linux
    aarch64 system through a bundled armhf system root. It reports what the
    display stack offers there and whether drawing reaches the screen, which
    decides whether an armhf build of the game is worth making.

    It prints one line per fact, flushes each line, and exits 0 when the
    centre pixel is red, 2 when drawing ran but the pixel is wrong, and 1
    when SDL, the context or a shader failed.

    HALO_PROBE_FRAMES sets how many frames are drawn (default 120).
*/

#include <SDL3/SDL.h>
#include <GLES3/gl3.h>

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>

/** The width of the window the probe draws into. */
#define PROBE_WIDTH 640
/** The height of the window the probe draws into. */
#define PROBE_HEIGHT 480
/** Frames drawn when HALO_PROBE_FRAMES is unset. */
#define PROBE_DEFAULT_FRAMES 120

/** A triangle covering the window's centre, in clip space. */
static const char *const probe_vertex_shader =
    "#version 300 es\n"
    "layout(location = 0) in vec2 in_position;\n"
    "void main(void)\n"
    "{\n"
    "    gl_Position = vec4(in_position, 0.0, 1.0);\n"
    "}\n";

/** Paints the triangle red. */
static const char *const probe_fragment_shader =
    "#version 300 es\n"
    "precision mediump float;\n"
    "out vec4 out_color;\n"
    "void main(void)\n"
    "{\n"
    "    out_color = vec4(1.0, 0.0, 0.0, 1.0);\n"
    "}\n";

/** The triangle's three vertices: (x, y) in clip space. */
static const GLfloat probe_triangle[6] = {
    -0.8f, -0.8f,
     0.8f, -0.8f,
     0.0f,  0.9f,
};

/** Print one line to stdout and flush it, so a reader sees each result as it
    happens. */
static void probe_print(const char *format, ...)
{
    va_list arguments;

    va_start(arguments, format);
    vprintf(format, arguments);
    va_end(arguments);
    fflush(stdout);
}

/** Compile one shader. Prints the shader's log and returns 0 on failure. */
static GLuint probe_compile_shader(GLenum type, const char *source)
{
    GLuint shader;
    GLint compiled = GL_FALSE;
    GLint log_length = 0;
    char *log;

    shader = glCreateShader(type);
    if (shader == 0) {
        probe_print("error: glCreateShader failed\n");
        return 0;
    }

    glShaderSource(shader, 1, &source, NULL);
    glCompileShader(shader);
    glGetShaderiv(shader, GL_COMPILE_STATUS, &compiled);
    if (compiled == GL_TRUE) {
        return shader;
    }

    glGetShaderiv(shader, GL_INFO_LOG_LENGTH, &log_length);
    if (log_length > 1) {
        log = (char *)malloc((size_t)log_length);
        if (log != NULL) {
            glGetShaderInfoLog(shader, log_length, NULL, log);
            probe_print("shader_log=%s\n", log);
            free(log);
        }
    }
    probe_print("error: the %s shader did not compile\n",
                type == GL_VERTEX_SHADER ? "vertex" : "fragment");
    glDeleteShader(shader);
    return 0;
}

/** Link the probe's shaders into one program. Prints the program's log and
    returns 0 on failure. */
static GLuint probe_link_program(GLuint vertex, GLuint fragment)
{
    GLuint program;
    GLint linked = GL_FALSE;
    GLint log_length = 0;
    char *log;

    program = glCreateProgram();
    if (program == 0) {
        probe_print("error: glCreateProgram failed\n");
        return 0;
    }

    glAttachShader(program, vertex);
    glAttachShader(program, fragment);
    glLinkProgram(program);
    glGetProgramiv(program, GL_LINK_STATUS, &linked);
    if (linked == GL_TRUE) {
        return program;
    }

    glGetProgramiv(program, GL_INFO_LOG_LENGTH, &log_length);
    if (log_length > 1) {
        log = (char *)malloc((size_t)log_length);
        if (log != NULL) {
            glGetProgramInfoLog(program, log_length, NULL, log);
            probe_print("program_log=%s\n", log);
            free(log);
        }
    }
    probe_print("error: the program did not link\n");
    glDeleteProgram(program);
    return 0;
}

/** How many frames to draw: HALO_PROBE_FRAMES, or PROBE_DEFAULT_FRAMES when
    it is unset, empty or not a positive number. */
static int probe_frame_count(void)
{
    const char *value;
    long frames;

    value = getenv("HALO_PROBE_FRAMES");
    if (value == NULL || *value == '\0') {
        return PROBE_DEFAULT_FRAMES;
    }

    frames = strtol(value, NULL, 10);
    if (frames < 1) {
        return PROBE_DEFAULT_FRAMES;
    }
    if (frames > 1000000) {
        frames = 1000000;
    }
    return (int)frames;
}

/** Create the window with an OpenGL ES 3.2 context, retrying with 3.0 if the
    context cannot be made. Returns 0 and prints SDL's error on failure. */
static int probe_create_context(SDL_Window **window, SDL_GLContext *context)
{
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_ES);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 3);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 2);

    *window = SDL_CreateWindow("OpenCE armhf probe", PROBE_WIDTH, PROBE_HEIGHT,
                               SDL_WINDOW_OPENGL);
    if (*window == NULL) {
        probe_print("error: SDL_CreateWindow: %s\n", SDL_GetError());
        return 0;
    }

    *context = SDL_GL_CreateContext(*window);
    if (*context == NULL) {
        probe_print("note: no OpenGL ES 3.2 context: %s\n", SDL_GetError());
        SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 0);
        SDL_DestroyWindow(*window);
        *window = SDL_CreateWindow("OpenCE armhf probe", PROBE_WIDTH,
                                   PROBE_HEIGHT, SDL_WINDOW_OPENGL);
        if (*window == NULL) {
            probe_print("error: SDL_CreateWindow: %s\n", SDL_GetError());
            return 0;
        }
        *context = SDL_GL_CreateContext(*window);
    }

    if (*context == NULL) {
        probe_print("error: SDL_GL_CreateContext: %s\n", SDL_GetError());
        return 0;
    }

    if (!SDL_GL_MakeCurrent(*window, *context)) {
        probe_print("error: SDL_GL_MakeCurrent: %s\n", SDL_GetError());
        return 0;
    }
    return 1;
}

int main(void)
{
    SDL_Window *window = NULL;
    SDL_GLContext context = NULL;
    const char *text;
    GLuint vertex = 0;
    GLuint fragment = 0;
    GLuint program = 0;
    GLuint vertex_array = 0;
    GLuint vertex_buffer = 0;
    GLint drawable_width = PROBE_WIDTH;
    GLint drawable_height = PROBE_HEIGHT;
    int frames;
    int drawn;
    int frame;
    Uint64 start;
    Uint64 elapsed;
    unsigned char pixel[4] = { 0, 0, 0, 0 };
    int status = 1;

    if (!SDL_Init(SDL_INIT_VIDEO)) {
        probe_print("error: SDL_Init: %s\n", SDL_GetError());
        return 1;
    }

    if (!probe_create_context(&window, &context)) {
        goto cleanup;
    }

    text = SDL_GetCurrentVideoDriver();
    probe_print("sdl_video_driver=%s\n", text != NULL ? text : "(none)");

    text = (const char *)glGetString(GL_VENDOR);
    probe_print("gl_vendor=%s\n", text != NULL ? text : "(none)");
    text = (const char *)glGetString(GL_RENDERER);
    probe_print("gl_renderer=%s\n", text != NULL ? text : "(none)");
    text = (const char *)glGetString(GL_VERSION);
    probe_print("gl_version=%s\n", text != NULL ? text : "(none)");
    probe_print("ptr_bytes=%zu\n", sizeof(void *));

    vertex = probe_compile_shader(GL_VERTEX_SHADER, probe_vertex_shader);
    if (vertex == 0) {
        goto cleanup;
    }
    fragment = probe_compile_shader(GL_FRAGMENT_SHADER, probe_fragment_shader);
    if (fragment == 0) {
        goto cleanup;
    }
    program = probe_link_program(vertex, fragment);
    if (program == 0) {
        goto cleanup;
    }

    glGenVertexArrays(1, &vertex_array);
    glBindVertexArray(vertex_array);
    glGenBuffers(1, &vertex_buffer);
    glBindBuffer(GL_ARRAY_BUFFER, vertex_buffer);
    glBufferData(GL_ARRAY_BUFFER, sizeof(probe_triangle), probe_triangle,
                 GL_STATIC_DRAW);
    glEnableVertexAttribArray(0);
    glVertexAttribPointer(0, 2, GL_FLOAT, GL_FALSE, 0, NULL);

    SDL_GetWindowSizeInPixels(window, &drawable_width, &drawable_height);
    if (drawable_width < 1) {
        drawable_width = 1;
    }
    if (drawable_height < 1) {
        drawable_height = 1;
    }
    glViewport(0, 0, drawable_width, drawable_height);
    glClearColor(0.0f, 0.0f, 0.0f, 1.0f);

    /* The probe measures drawing, not waiting for the display. */
    SDL_GL_SetSwapInterval(0);

    frames = probe_frame_count();
    drawn = 0;
    start = SDL_GetTicks();
    for (frame = 0; frame < frames; frame++) {
        SDL_Event event;

        while (SDL_PollEvent(&event)) {
            /* The probe ignores input. */
        }

        glClear(GL_COLOR_BUFFER_BIT);
        glUseProgram(program);
        glBindVertexArray(vertex_array);
        glDrawArrays(GL_TRIANGLES, 0, 3);
        glBindVertexArray(0);

        if (frame == frames - 1) {
            /* Read the centre before the last swap shows the frame. */
            glReadPixels(drawable_width / 2, drawable_height / 2, 1, 1,
                         GL_RGBA, GL_UNSIGNED_BYTE, pixel);
        }

        SDL_GL_SwapWindow(window);
        drawn++;
    }
    elapsed = SDL_GetTicks() - start;

    probe_print("frames=%d ms=%llu\n", drawn, (unsigned long long)elapsed);
    probe_print("center=%u,%u,%u\n", (unsigned)pixel[0], (unsigned)pixel[1],
                (unsigned)pixel[2]);

    if (pixel[0] > 200 && pixel[1] < 50 && pixel[2] < 50) {
        status = 0;
    } else {
        status = 2;
    }

cleanup:
    if (vertex_buffer != 0) {
        glDeleteBuffers(1, &vertex_buffer);
    }
    if (vertex_array != 0) {
        glDeleteVertexArrays(1, &vertex_array);
    }
    if (program != 0) {
        glDeleteProgram(program);
    }
    if (vertex != 0) {
        glDeleteShader(vertex);
    }
    if (fragment != 0) {
        glDeleteShader(fragment);
    }
    if (context != NULL) {
        SDL_GL_DestroyContext(context);
    }
    if (window != NULL) {
        SDL_DestroyWindow(window);
    }
    SDL_Quit();

    return status;
}
