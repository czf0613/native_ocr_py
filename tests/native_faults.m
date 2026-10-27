// Loaded only by isolated test children; never linked into the product extension.
#import <Foundation/Foundation.h>
#import <Vision/Vision.h>
#import <objc/runtime.h>
#include <stdatomic.h>
#include <unistd.h>

static atomic_int mode;
static atomic_int entered;
static atomic_int gate;
static atomic_int completed;
static IMP original_perform;
static IMP original_languages;

static BOOL injected_perform(id self, SEL selector, NSArray *requests, NSError **error)
{
    atomic_store(&entered, 1);
    @try
    {
        if (atomic_load(&mode) == 1)
        {
            if (error)
            {
                *error = [NSError errorWithDomain:@"ocr.test.injected" code:4826 userInfo:nil];
            }
            return NO;
        }
        if (atomic_load(&mode) == 2)
        {
            @throw [NSException exceptionWithName:@"OCRTestException" reason:@"injected" userInfo:nil];
        }
        if (atomic_load(&mode) == 3)
        {
            while (!atomic_load(&gate))
            {
                usleep(1000);
            }
        }
        return ((BOOL (*)(id, SEL, NSArray *, NSError **))original_perform)(self, selector, requests, error);
    }
    @finally
    {
        atomic_store(&completed, 1);
    }
}

static NSArray *injected_languages(id self, SEL selector, NSError **error)
{
    if (atomic_load(&mode) == 1)
    {
        if (error)
        {
            *error = [NSError errorWithDomain:@"ocr.test.injected" code:7319 userInfo:nil];
        }
        return nil;
    }
    if (atomic_load(&mode) == 2)
    {
        @throw [NSException exceptionWithName:@"OCRTestLanguageException" reason:@"injected" userInfo:nil];
    }
    return ((NSArray *(*)(id, SEL, NSError **))original_languages)(self, selector, error);
}

void ocr_test_install(int value)
{
    atomic_store(&mode, value);
    atomic_store(&entered, 0);
    atomic_store(&gate, 0);
    atomic_store(&completed, 0);
    if (!original_perform)
    {
        Method method = class_getInstanceMethod([VNImageRequestHandler class], @selector(performRequests:error:));
        original_perform = method_setImplementation(method, (IMP)injected_perform);
        method = class_getInstanceMethod([VNRecognizeTextRequest class], @selector(supportedRecognitionLanguagesAndReturnError:));
        original_languages = method_setImplementation(method, (IMP)injected_languages);
    }
}

int ocr_test_entered(void) { return atomic_load(&entered); }
int ocr_test_completed(void) { return atomic_load(&completed); }
void ocr_test_unblock(void) { atomic_store(&gate, 1); }
