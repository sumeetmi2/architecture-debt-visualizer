package com.example.templates.helpers;

import com.example.templates.TemplateHelper;

/** Reference implementation of the documented helper-registration pattern. */
public class UpperCaseHelper implements TemplateHelper {
    @Override
    public String apply(Object value) {
        return value == null ? "" : value.toString().toUpperCase();
    }
}
